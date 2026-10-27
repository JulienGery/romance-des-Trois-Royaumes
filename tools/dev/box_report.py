import re,sys,collections
rows=[]
for l in open(sys.argv[1]):
    m=re.match(r'\[box\] (\S+) mode=(\d+) type=(\d+) len=(\d+) x=(-?\d+) y=(-?\d+) w=(-?\d+) h=(-?\d+) tx=(-?\d+) ty=(-?\d+) mw=(-?\d+) mh=(-?\d+) cw=(\d+)',l)
    if m: rows.append((m.group(1),)+tuple(int(x) for x in m.groups()[1:]))
agg=collections.defaultdict(list)
for fn,mode,typ,L,x,y,w,h,tx,ty,mw,mh,cw in rows:
    lines=max(1,round((mh+0)/ (cw+1))) if mh else 0  # approx (line step unknown); refined below
    agg[(fn,mode,typ)].append((mh,x,y,w,h,tx,ty,mw))
for k,v in sorted(agg.items()):
    mhs=sorted(set(a[0] for a in v))
    bad=[a for a in v if a[2]<0 or a[2]+a[4]>240 or a[6]+a[0]>a[4] or a[5]<0 or a[5]+a[7]>a[3]]
    print(k,'n=%d distinct mh=%s'%(len(v),mhs[:14]),'| y range %d..%d  bottom max %d  h %d..%d | text overflow(bottom) max %d  width-overflow max %d | bad=%d'%(
        min(a[2] for a in v),max(a[2] for a in v),max(a[2]+a[4] for a in v),min(a[4] for a in v),max(a[4] for a in v),
        max(a[6]+a[0]-a[4] for a in v),max(a[5]+a[7]-a[3] for a in v),len(bad)))
