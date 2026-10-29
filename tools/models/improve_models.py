#!/usr/bin/env python3
"""Améliore la géométrie des modèles 3D des yo-kai / personnages de LINKDATA_A.BIN (modèles `_M1G` dans les entrées « binary »).

  improve_models.py [--src LINKDATA_A.BIN] [--dst out.BIN] [--level 1] [--entries 16300,16301] [--no-subdivide] [--no-smooth] [--check]

Deux traitements, indépendants (voir docs/MODELES_3D.md) :
  * lissage des normales : les sommets confondus en position (couture d'UV) reçoivent la même normale
    moyenne, sauf arête vive (écart > ~45°) → plus de coupure d'éclairage aux coutures. La taille ne change pas.
  * subdivision courbe : chaque triangle devient 4 (milieux d'arêtes posés sur l'arête cubique « PN triangles » définie par
    les normales ; les sommets d'origine ne bougent pas, les arêtes vives restent droites). Silhouettes plus rondes.
    Attributs interpolés : UV, normale, couleur, poids d'os (fusion des 4 meilleurs). Aucun tampon de plus de 65 535 sommets.
"""
import argparse, os, struct, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path[:0] = [HERE, os.path.join(ROOT, 'tools'), os.path.join(ROOT, 'externals', 'LINKDATA-explorer')]
from g1mg import *  # noqa: E402,F403

SEM_POS, SEM_W, SEM_BONE, SEM_NRM, SEM_UV, SEM_COL = 0, 1, 2, 3, 5, 10
HARD_COS = 0.7            # en dessous, les normales d'un même point sont considérées comme une arête vive
MAX_VERTS = 65535
BUDGET = 20000            # un tampon n'est subdivisé que si le résultat reste sous ce nombre de sommets (les petits modèles reçoivent plusieurs niveaux)
CREASE_DEG = 40.0         # angle dièdre au-delà duquel une arête reste droite (cylindres, pointes) ; en dessous elle est arrondie (dômes)


class Buf:
    """Un tampon de sommets sous forme de matrice d'octets (n, stride) + ses attributs."""
    def __init__(self, stride, data, attrs):
        self.stride, self.attrs = stride, {s: (o, t) for _, o, t, s in attrs}
        self.attr_list = attrs
        self.v = np.frombuffer(data, np.uint8).reshape(-1, stride).copy()

    def f32(self, sem, k):
        o, _ = self.attrs[sem]
        return np.ascontiguousarray(self.v[:, o:o + 4 * k]).view('<f4').reshape(len(self.v), k)

    def set_f32(self, sem, a):
        o, _ = self.attrs[sem]
        a = np.ascontiguousarray(a, '<f4')
        self.v[:, o:o + 4 * a.shape[1]] = a.view(np.uint8).reshape(len(self.v), -1)


def weld_groups(pos):
    q = np.round(pos * 2000).astype(np.int64)
    _, g = np.unique(q, axis=0, return_inverse=True)
    return g.reshape(-1)


def welded_normals(buf):
    """(normale lissée par sommet, drapeau « arête vive » par sommet)."""
    pos, n = buf.f32(SEM_POS, 3), buf.f32(SEM_NRM, 3)
    g = weld_groups(pos)
    ng = int(g.max()) + 1
    s = np.zeros((ng, 3)); np.add.at(s, g, n)
    ln = np.linalg.norm(s, axis=1, keepdims=True)
    avg = np.where(ln > 1e-6, s / np.maximum(ln, 1e-9), 0)
    dots = np.einsum('ij,ij->i', n, avg[g])
    mn = np.full(ng, 2.0); np.minimum.at(mn, g, dots)
    hard = (mn < HARD_COS) | (ln[:, 0] < 1e-6)
    return avg[g].astype('f4'), hard[g]


def sharp_edges(buf, tris, g, crease_deg):
    """Clés (g_a * G + g_b, sommets soudés) des arêtes dont l'angle dièdre dépasse crease_deg : le maillage d'origine y est volontairement anguleux."""
    pos = buf.f32(SEM_POS, 3).astype(np.float64)
    fn = np.cross(pos[tris[:, 1]] - pos[tris[:, 0]], pos[tris[:, 2]] - pos[tris[:, 0]])
    ln = np.linalg.norm(fn, axis=1, keepdims=True)
    fn = np.where(ln > 1e-12, fn / np.maximum(ln, 1e-12), 0)
    G = int(g.max()) + 1
    ga = g[tris]
    a, b = ga[:, [0, 1, 2]].ravel(), ga[:, [1, 2, 0]].ravel()
    key = np.minimum(a, b) * G + np.maximum(a, b)
    face = np.repeat(np.arange(len(tris)), 3)
    o = np.argsort(key, kind='stable'); key, face = key[o], face[o]
    first = np.r_[0, np.flatnonzero(np.diff(key)) + 1]
    gid = np.repeat(np.arange(len(first)), np.diff(np.r_[first, len(key)]))
    d = np.einsum('ij,ij->i', fn[face], fn[face[first][gid]])
    d = np.where((np.linalg.norm(fn[face], axis=1) > 0) & (np.linalg.norm(fn[face[first][gid]], axis=1) > 0), d, 1.0)
    mn = np.minimum.reduceat(d, first)
    return key[first][mn < np.cos(np.radians(crease_deg))], G


def crease_curve_corrections(buf, keys, g, G, crease_deg):
    """Pour chaque arête vive (clé triée `keys`) : décalage du milieu pour que les arêtes vives forment une courbe lisse (Catmull-Rom)
    quand le contour tourne peu (bord d'un bol) ; aux coins (>= 3 arêtes vives, ou virage > crease_deg) l'arête reste droite."""
    pos = buf.f32(SEM_POS, 3).astype(np.float64)
    rep = np.zeros((G, 3)); rep[g[::-1]] = pos[::-1]               # position d'un groupe de sommets soudés
    nb = {}
    for k in keys.tolist():
        a, b = divmod(k, G); nb.setdefault(a, []).append(b); nb.setdefault(b, []).append(a)
    cosmax = np.cos(np.radians(crease_deg))
    def other(v, w):                                                # voisin de v sur la courbe, autre que w (None si coin)
        l = nb[v]
        if len(l) != 2: return None
        r = l[0] if l[1] == w else l[1]
        u1, u2 = rep[v] - rep[r], rep[w] - rep[v]                    # direction d'arrivée / de sortie en v
        c = u1 @ u2 / (np.linalg.norm(u1) * np.linalg.norm(u2) + 1e-12)
        return r if c >= cosmax else None
    corr = np.zeros((len(keys), 3))
    for n, k in enumerate(keys.tolist()):
        a, b = divmod(k, G)
        d = rep[b] - rep[a]
        ra, rb = other(a, b), other(b, a)
        ta = (rep[b] - rep[ra]) / 2 if ra is not None else d
        tb = (rep[rb] - rep[a]) / 2 if rb is not None else d
        corr[n] = (ta - tb) / 8
    return corr


def smooth_normals(buf):
    avg, hard = welded_normals(buf)
    n = buf.f32(SEM_NRM, 3)
    buf.set_f32(SEM_NRM, np.where(hard[:, None], n, avg))


def merge_skin(wa, ia, wb, ib):
    """Poids/indices (n,4) uint8 de deux sommets → fusion 50/50, 4 meilleurs os, somme 255."""
    n = len(wa)
    wo, io = np.zeros((n, 4), np.uint8), np.zeros((n, 4), np.uint8)
    for k in range(n):
        d = {}
        for w, i in ((wa, ia), (wb, ib)):
            for s in range(4):
                if w[k, s]: d[i[k, s]] = d.get(i[k, s], 0) + w[k, s] / 2
        top = sorted(d.items(), key=lambda x: -x[1])[:4]
        tot = sum(x[1] for x in top) or 1
        q = [int(round(255 * x[1] / tot)) for x in top]
        q[0] += 255 - sum(q)
        for s, ((b, _), w) in enumerate(zip(top, q)):
            io[k, s], wo[k, s] = b, w
    return wo, io


def subdivide_range(buf, tris, vs, vc, nrm, hard, sharp=None):
    """Un niveau pour un sous-maillage : renvoie (nouveaux sommets (m,stride), triangles remappés).
    tris : indices absolus (dans le tampon) ; les nouveaux sommets reçoivent les numéros vc.. (relatifs à vs)."""
    i0, i1 = tris[:, [0, 1, 2]], tris[:, [1, 2, 0]]
    ea, eb = np.minimum(i0, i1).ravel(), np.maximum(i0, i1).ravel()
    key = ea * (len(buf.v) + 1) + eb
    uk, inv = np.unique(key, return_inverse=True)
    inv = inv.reshape(-1, 3)
    A, B = uk // (len(buf.v) + 1), uk % (len(buf.v) + 1)
    pos = buf.f32(SEM_POS, 3).astype(np.float64)
    pa, pb = pos[A], pos[B]
    d = pb - pa
    fnorm = np.cross(pos[tris[:, 1]] - pos[tris[:, 0]], pos[tris[:, 2]] - pos[tris[:, 0]])
    fl = np.linalg.norm(fnorm, axis=1, keepdims=True)
    fnorm = np.where(fl > 1e-12, fnorm / np.maximum(fl, 1e-12), 0)
    fe = np.zeros((len(uk), 3)); fe[inv.ravel()] = np.repeat(fnorm, 3, axis=0)   # normale d'une face portant l'arête
    use = np.where(hard[:, None], buf.f32(SEM_NRM, 3).astype(np.float64), nrm.astype(np.float64))   # normale propre aux sommets d'angle, lissée sinon
    def end_normal(V):                    # normale du sommet si elle est cohérente avec la face (< 30°), sinon celle de la face (pas de courbure)
        nv = use[V]
        return np.where((np.einsum('ij,ij->i', nv, fe) >= np.cos(np.radians(30)))[:, None], nv, fe)
    na, nb = end_normal(A), end_normal(B)
    mid = (pa + pb) / 2 + ((np.einsum('ij,ij->i', d, nb))[:, None] * nb - (np.einsum('ij,ij->i', d, na))[:, None] * na) / 8
    if sharp is not None and len(sharp[0]):   # arête vive : courbe lisse le long du contour (droite aux coins)
        keys, g, G, corr = sharp
        k = np.minimum(g[A], g[B]) * G + np.maximum(g[A], g[B])
        j = np.clip(np.searchsorted(keys, k), 0, len(keys) - 1)
        hit = keys[j] == k
        mid = np.where(hit[:, None], (pa + pb) / 2 + corr[j], mid)
    new = buf.v[A].copy()
    def put(sem, arr):
        o, t = buf.attrs[sem]; arr = np.ascontiguousarray(arr, '<f4')
        new[:, o:o + arr.shape[1] * 4] = arr.view(np.uint8).reshape(len(new), -1)
    def col(sem, k):
        o, _ = buf.attrs[sem]
        return np.ascontiguousarray(buf.v[:, o:o + 4 * k]).view('<f4').reshape(len(buf.v), k)[:]
    put(SEM_POS, mid)
    nn = col(SEM_NRM, 3)
    m = nn[A] + nn[B]
    ln = np.linalg.norm(m, axis=1, keepdims=True)
    put(SEM_NRM, np.where(ln > 1e-6, m / np.maximum(ln, 1e-9), nn[A]))
    if SEM_UV in buf.attrs and buf.attrs[SEM_UV][1] == 1:
        uv = col(SEM_UV, 2); put(SEM_UV, (uv[A] + uv[B]) / 2)
    if SEM_COL in buf.attrs:
        o, _ = buf.attrs[SEM_COL]
        new[:, o:o + 4] = ((buf.v[A, o:o + 4].astype(np.int32) + buf.v[B, o:o + 4]) // 2).astype(np.uint8)
    if SEM_W in buf.attrs and SEM_BONE in buf.attrs:
        ow, ob = buf.attrs[SEM_W][0], buf.attrs[SEM_BONE][0]
        wa, wb = buf.v[A, ow:ow + 4], buf.v[B, ow:ow + 4]
        ia, ib = buf.v[A, ob:ob + 4], buf.v[B, ob:ob + 4]
        diff = np.where((wa != wb).any(1) | (ia != ib).any(1))[0]
        if len(diff):
            wo, io = merge_skin(wa[diff], ia[diff], wb[diff], ib[diff])
            new[diff, ow:ow + 4] = wo; new[diff, ob:ob + 4] = io
    mi = (inv + vc)                       # indices relatifs des milieux
    a, b, c = tris[:, 0] - vs, tris[:, 1] - vs, tris[:, 2] - vs
    m01, m12, m20 = mi[:, 0], mi[:, 1], mi[:, 2]
    out = np.stack([np.stack(t, 1) for t in ((a, m01, m20), (m01, m12, m20), (m01, b, m12), (m20, m12, c))], 1).reshape(-1, 3)   # les 4 enfants d'un triangle restent côte à côte (bandes plus courtes)
    return new, out


def subdivide_model(vbufs, attrsets, ibufs, subs, levels, crease=CREASE_DEG, budget=BUDGET):
    """vbufs [(stride,count,data)], ibufs [ndarray], subs [liste de 14 mots]. Retourne (vbufs, ibufs, subs) ou None si rien n'a changé."""
    bufs = [Buf(s, d, a) for (s, c, d), a in zip(vbufs, attrsets)]
    if any(SEM_POS not in b.attrs or SEM_NRM not in b.attrs for b in bufs): return None
    subs = [list(s) for s in subs]
    ibufs = [a.copy() for a in ibufs]
    done = False
    for _ in range(levels):
        nb_ok = []
        for bi, buf in enumerate(bufs):
            mine = sorted([s for s in subs if s[7] == bi], key=lambda s: s[12])
            tri = {id(s): strip_to_tris(ibufs[bi][s[12]:s[12] + s[13]]) for s in mine}
            est = len(buf.v) + sum(len(t) * 3 // 2 + 3 for t in tri.values())
            nb_ok.append(est <= min(MAX_VERTS, budget) and len(buf.v) > 0)
        for bi, buf in enumerate(bufs):
            if not nb_ok[bi]: continue
            nrm, hard = welded_normals(buf)
            mine = sorted([s for s in subs if s[7] == bi], key=lambda s: s[12])
            alltris = [strip_to_tris(ibufs[bi][s[12]:s[12] + s[13]]) for s in mine]
            alltris = np.concatenate(alltris) if alltris else np.zeros((0, 3), np.int64)
            sharp = None
            if crease and len(alltris):
                g = weld_groups(buf.f32(SEM_POS, 3)); keys, G = sharp_edges(buf, alltris, g, crease); sharp = (keys, g, G, crease_curve_corrections(buf, keys, g, G, crease))
            blocks, idx_out, vpos, ipos = [], [], 0, 0
            for s in mine:
                vs, vc = s[10], s[11]
                t = strip_to_tris(ibufs[bi][s[12]:s[12] + s[13]])
                if len(t):
                    new, tr = subdivide_range(buf, t, vs, vc, nrm, hard, sharp)
                else:
                    new, tr = buf.v[:0], np.zeros((0, 3), np.int64)
                if vc + len(new) + vpos > MAX_VERTS: raise OverflowError
                blocks.append(np.concatenate([buf.v[vs:vs + vc], new]))
                st = tris_to_strip(tr + vpos) if len(tr) else np.zeros(0, np.int64)
                s_new = (vpos, vc + len(new), ipos, len(st))
                idx_out.append(st); s[10:14] = s_new
                vpos += vc + len(new); ipos += len(st)
            buf.v = np.concatenate(blocks) if blocks else buf.v
            ibufs[bi] = np.concatenate(idx_out).astype(np.uint16) if idx_out else ibufs[bi]
            done = True
    if not done: return None
    return [(b.stride, len(b.v), b.v.tobytes()) for b in bufs], ibufs, subs


def process_m1g(m1g, levels=1, smooth=True, subdivide=True, crease=CREASE_DEG, budget=BUDGET):
    """Retourne le `_M1G` modifié, ou None."""
    r = find_gm1g(m1g)
    if not r: return None
    head, secs, tail = parse_gm1g(m1g[r[0]:r[0] + r[1]])
    sub, ib, vb, at = (get(secs, t) for t in (SEC_SUB, SEC_IDX, SEC_VERT, SEC_ATTR))
    if not (sub and ib and vb and at) or min(len(x[0].body) for x in (sub, ib, vb, at)) < 12: return None
    vbs, ibs, subs, sets = parse_vbufs(vb[0]), parse_ibufs(ib[0]), parse_subs(sub[0]), parse_attrs(at[0])
    if smooth:
        bufs = [Buf(s, d, a) for (s, c, d), a in zip(vbs, sets)]
        if all(SEM_POS in b.attrs and SEM_NRM in b.attrs for b in bufs):
            for b in bufs: smooth_normals(b)
            vbs = [(b.stride, len(b.v), b.v.tobytes()) for b in bufs]
    if subdivide and levels > 0:
        try:
            res = subdivide_model(vbs, sets, ibs, subs, levels, crease, budget)
        except OverflowError:
            res = None
        if res: vbs, ibs, subs = res
    vb[0].body = build_vbufs(vbs)
    ib[0].body = build_ibufs(ibs)
    sub[0].body = b''.join(struct.pack('<14I', *s) for s in subs)
    g = build_gm1g(head, secs, tail)
    out = bytearray(m1g[:r[0]]) + g + m1g[r[0] + r[1]:]
    out[8:12] = struct.pack('<I', len(out))
    return bytes(out)


def process_entry(entry, **kw):
    """Entrée « binary » d'un modèle (table de décalages + fichiers) → entrée modifiée ou None."""
    files = split_models(entry)
    if not files or not any(m == b'_M1G' for _, _, m in files): return None
    n = len(files)
    first = files[0][0]
    out = bytearray(entry[:first])
    changed = False
    for k, (o, sz, mg) in enumerate(files):
        blob = entry[o:o + sz]
        if mg == b'_M1G':
            real = struct.unpack_from('<I', blob, 8)[0]
            new = process_m1g(blob[:real], **kw)
            if new is not None:
                blob, changed = new, True
        while len(out) % 16: out.append(0)
        struct.pack_into('<I', out, 4 + 4 * k, len(out))
        out += blob
    return bytes(out) if changed else None


def model_items(arc, only=None, **kw):
    """{entrée: (octets, compressé)} pour tous les modèles de personnages (utilisé par apply_translation.py)."""
    items = {}
    for e in arc.entries:
        if e.file_type != 'binary' or not 16000 <= e.index <= 18800 or (only and e.index not in only): continue
        d = arc.read_entry_decompressed(e.index)
        try:
            new = process_entry(d, **kw)
        except Exception as ex:      # modèle inattendu : on le laisse tel quel
            print(f'  entrée {e.index} ignorée : {ex!r}'); continue
        if new: items[e.index] = (new, True)
    return items


if __name__ == '__main__':
    from linkdata_engine import LinkDataArchive
    from patch_linkdata import patch_many
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=os.path.join(ROOT, 'work/rom/romfs_dir/Data/LINKDATA_A.BIN'))
    ap.add_argument('--dst'); ap.add_argument('--level', type=int, default=1)
    ap.add_argument('--crease', type=float, default=CREASE_DEG, help='angle dièdre (°) au-delà duquel une arête reste vive'); ap.add_argument('--budget', type=int, default=BUDGET, help='nb max de sommets par tampon après subdivision'); ap.add_argument('--entries'); ap.add_argument('--no-subdivide', action='store_true'); ap.add_argument('--no-smooth', action='store_true')
    ap.add_argument('--check', action='store_true', help='ne rien écrire, afficher les statistiques')
    a = ap.parse_args()
    arc = LinkDataArchive(a.src)
    only = {int(x) for x in a.entries.split(',')} if a.entries else None
    items = model_items(arc, only, levels=a.level, smooth=not a.no_smooth, subdivide=not a.no_subdivide, crease=a.crease, budget=a.budget)
    print(f'{len(items)} entrées de modèles modifiées')
    if not a.check and a.dst:
        patch_many(a.src, a.dst, items); print('écrit', a.dst)
