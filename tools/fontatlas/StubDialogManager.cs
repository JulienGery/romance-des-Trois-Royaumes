using Konnect.Contract.DataClasses.Management.Dialog;
using Konnect.Contract.Management.Dialog;

namespace Level5FontAtlas;

/// <summary>Non-interactive dialog manager; callers fall back to the field defaults.</summary>
internal class StubDialogManager : IDialogManager
{
    public IList<DialogField> DialogFields { get; } = [];

    public Task<bool> ShowDialog(params DialogField[] fields) => Task.FromResult(false);
}
