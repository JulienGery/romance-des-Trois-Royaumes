using System.Text;
using System.Text.Json;
using Level5FontAtlas;
using plugin_level5.Common.Archive;
using plugin_level5.Common.Archive.Models;
using plugin_level5.Common.Font;
using plugin_level5.Common.Font.Models;
using plugin_level5.Common.Image;
using plugin_level5.Common.Image.Models;
using SixLabors.ImageSharp;
using SixLabors.ImageSharp.PixelFormats;

// Usage: Level5FontAtlas <font.xf | FNT.bin> [outputDir] [--all] [--chars <extra characters>] [--font large|small]
//   Default: only the glyphs needed for French are packed into a new atlas (PNG + JSON + BMFont .fnt).
//   --all : keep every glyph of the font.
var positional = args.Where(a => !a.StartsWith("--")).ToList();
if (args.Length < 1 || args[0].StartsWith("--"))
{
    Console.Error.WriteLine("Usage: Level5FontAtlas <font.xf> [outputDir] [--all] [--chars <extra>] [--font large|small]");
    return 1;
}

string inputPath = args[0];
string outputDir = args.Length > 1 && !args[1].StartsWith("--") ? args[1] : Path.GetFileNameWithoutExtension(inputPath) + "_atlas";
bool keepAll = args.Contains("--all");
int charsIdx = Array.IndexOf(args, "--chars");
string extraChars = charsIdx >= 0 && charsIdx + 1 < args.Length ? args[charsIdx + 1] : "";
int fontIdx = Array.IndexOf(args, "--font");
bool useSmall = fontIdx >= 0 && fontIdx + 1 < args.Length && args[fontIdx + 1] == "small";
Directory.CreateDirectory(outputDir);

using var file = File.OpenRead(inputPath);
var buffer = new MemoryStream();
file.CopyTo(buffer);
buffer.Position = 0;

if (!IsXpck(buffer))
{
    Console.Error.WriteLine("Input must be an XPCK font archive (FNT.bin + .xi textures).");
    return 1;
}

ArchiveData archive = new XpckReader().Read(buffer);
ArchiveNamedEntry fntEntry = archive.Files.FirstOrDefault(f => f.Name.Equals("FNT.bin", StringComparison.OrdinalIgnoreCase))
    ?? throw new InvalidOperationException("No FNT.bin found in archive.");
ArchiveNamedEntry xiEntry = archive.Files.FirstOrDefault(f => f.Name.EndsWith(".xi", StringComparison.OrdinalIgnoreCase))
    ?? throw new InvalidOperationException("No .xi texture found in archive.");

fntEntry.Content.Position = 0;
int version = new FontVersionReader().Peek(fntEntry.Content);
FontData font = new FontReaderFactory().Create(version).Read(fntEntry.Content);
FontGlyphsData glyphSet = useSmall ? font.SmallFont : font.LargeFont;

xiEntry.Content.Position = 0;
int imgVersion = new ImageVersionReader().Peek(xiEntry.Content);
ImageRawData raw = new ImageReaderFactory().Create(imgVersion).Read(xiEntry.Content);
ImageData imageData = await new ImageDecoder(new StubDialogManager()).Decode(raw);
Image<Rgba32> source = imageData.Image.GetImage();
source.SaveAsPng(Path.Combine(outputDir, "source_texture.png"));

HashSet<int> wanted = keepAll
    ? glyphSet.Glyphs.Keys.Select(c => (int)c).ToHashSet()
    : FrenchCharset.Build(extraChars).Append(glyphSet.FallbackCharacter).ToHashSet();

var selected = glyphSet.Glyphs.Values.Where(g => wanted.Contains(g.CodePoint)).OrderBy(g => g.CodePoint).ToList();
int[] missing = wanted.Where(c => !glyphSet.Glyphs.ContainsKey((char)c)).OrderBy(c => c).ToArray();

// Extract each glyph as white + coverage in alpha.
var crops = new List<(FontGlyphData Glyph, Image<Rgba32>? Image)>();
foreach (FontGlyphData g in selected)
    crops.Add((g, ExtractGlyph(source, g, font.Version.Version)));

// Shelf packing, 1px padding.
const int pad = 1;
int atlasWidth = 512;
var placements = new Dictionary<int, (int X, int Y)>();
int cx = pad, cy = pad, rowH = 0;
foreach (var (g, img) in crops.Where(c => c.Image != null).OrderByDescending(c => c.Image!.Height))
{
    if (cx + img!.Width + pad > atlasWidth) { cx = pad; cy += rowH + pad; rowH = 0; }
    placements[g.CodePoint] = (cx, cy);
    cx += img.Width + pad;
    rowH = Math.Max(rowH, img.Height);
}
int atlasHeight = 1;
while (atlasHeight < cy + rowH + pad) atlasHeight <<= 1;

using var atlas = new Image<Rgba32>(atlasWidth, atlasHeight);
foreach (var (g, img) in crops.Where(c => c.Image != null))
{
    var (px, py) = placements[g.CodePoint];
    Image<Rgba32> glyphImage = img!;
    atlas.ProcessPixelRows(glyphImage, (dst, src) =>
    {
        for (int y = 0; y < src.Height; y++)
            src.GetRowSpan(y).CopyTo(dst.GetRowSpan(py + y).Slice(px, src.Width));
    });
}
atlas.SaveAsPng(Path.Combine(outputDir, "atlas.png"));

var glyphEntries = crops.Select(c => new
{
    codePoint = (int)c.Glyph.CodePoint,
    character = char.ConvertFromUtf32(c.Glyph.CodePoint is >= 0xD800 and <= 0xDFFF ? 0xFFFD : c.Glyph.CodePoint),
    x = placements.TryGetValue(c.Glyph.CodePoint, out var p) ? p.X : 0,
    y = p.Y,
    width = c.Image?.Width ?? 0,
    height = c.Image?.Height ?? 0,
    offsetX = (int)c.Glyph.Description.X,
    offsetY = (int)c.Glyph.Description.Y,
    advance = c.Glyph.Width
}).ToArray();

File.WriteAllText(Path.Combine(outputDir, "atlas.json"), JsonSerializer.Serialize(new
{
    atlasWidth,
    atlasHeight,
    lineHeight = glyphSet.MaxHeight,
    fallbackCodePoint = (int)glyphSet.FallbackCharacter,
    glyphs = glyphEntries
}, new JsonSerializerOptions { WriteIndented = true, Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping }));

// BMFont text format (usable by most engines/tools).
var fnt = new StringBuilder();
fnt.AppendLine($"info face=\"{Path.GetFileNameWithoutExtension(inputPath)}\" size={glyphSet.MaxHeight} bold=0 italic=0");
fnt.AppendLine($"common lineHeight={glyphSet.MaxHeight} base={glyphSet.MaxHeight} scaleW={atlasWidth} scaleH={atlasHeight} pages=1 packed=0");
fnt.AppendLine("page id=0 file=\"atlas.png\"");
fnt.AppendLine($"chars count={glyphEntries.Length}");
foreach (var e in glyphEntries)
    fnt.AppendLine($"char id={e.codePoint} x={e.x} y={e.y} width={e.width} height={e.height} xoffset={e.offsetX} yoffset={e.offsetY} xadvance={e.advance} page=0 chnl=15");
File.WriteAllText(Path.Combine(outputDir, "atlas.fnt"), fnt.ToString());

Console.WriteLine($"Atlas {atlasWidth}x{atlasHeight}: {glyphEntries.Length} glyphs written to {outputDir}");
if (missing.Length > 0)
    Console.WriteLine($"Not in font ({missing.Length}): {string.Concat(missing.Select(c => char.ConvertFromUtf32(c)))}");
return 0;

static bool IsXpck(Stream s)
{
    var magic = new byte[4];
    s.Position = 0;
    int read = s.Read(magic);
    s.Position = 0;
    return read == 4 && magic[0] == 'X' && magic[1] == 'P' && magic[2] == 'C' && magic[3] == 'K';
}

// Ctr fonts store each glyph in one color channel (Index 0=R, 1=G, 2=B). Same math as GlyphCtrProvider.
static Image<Rgba32>? ExtractGlyph(Image<Rgba32> source, FontGlyphData g, int fontVersion)
{
    int w = g.Description.Width, h = g.Description.Height;
    if (w <= 0 || h <= 0)
        return null;

    var result = new Image<Rgba32>(w, h);
    for (int y = 0; y < h; y++)
    for (int x = 0; x < w; x++)
    {
        int sx = g.Location.X + x, sy = g.Location.Y + y;
        if (sx >= source.Width || sy >= source.Height)
            continue;

        Rgba32 px = source[sx, sy];
        byte v = g.Location.Index switch { 0 => px.R, 1 => px.G, _ => px.B };
        float a = fontVersion == 0 ? Math.Clamp((v - 123f) * 255f / (255f - 123f), 0f, 255f) : v;
        result[x, y] = new Rgba32(255, 255, 255, (byte)a);
    }

    return result;
}
