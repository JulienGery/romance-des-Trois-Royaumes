namespace Level5FontAtlas;

internal static class FrenchCharset
{
    private const string Letters = "àâäæçéèêëîïôöœùûüÿÀÂÄÆÇÉÈÊËÎÏÔÖŒÙÛÜŸ";
    private const string Punctuation = "«»‘’“”„…–—‐€£°·•×÷±§©®™′″   ";
    private const string Fullwidth = "　";

    public static IEnumerable<int> Build(string extra)
    {
        var set = new HashSet<int>();
        for (int c = 0x20; c <= 0x7E; c++)
            set.Add(c);

        foreach (char c in Letters + Punctuation + Fullwidth + extra)
            set.Add(c);

        return set;
    }
}
