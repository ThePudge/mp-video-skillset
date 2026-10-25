// MP Studio launcher — by @mohammadpour.bi (MIT). Built into "MP Studio.exe" (the repo's one start file)
// so it can carry the MP icon; a .bat cannot. It only runs mp-studio\tools\bootstrap.ps1, which installs
// what is missing on the first run and then opens MP Studio. Rebuild with mp-studio\tools\launcher\build.bat.
using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;

static class Launcher
{
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    static extern int MessageBox(IntPtr hWnd, string text, string caption, uint type);

    [STAThread]
    static int Main()
    {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        string script = Path.Combine(root, "mp-studio", "tools", "bootstrap.ps1");
        if (!File.Exists(script))
        {
            MessageBox(IntPtr.Zero, "Keep \"MP Studio.exe\" next to the mp-studio folder.\n\nNot found:\n" + script, "MP Studio", 0x10);
            return 1;
        }
        // First run (no Python environment yet): show the window so the owner sees the install progress.
        // Later runs: the window only hosts the local server, so it starts minimized.
        bool firstRun = !File.Exists(Path.Combine(root, ".venv", ".installed"));
        var psi = new ProcessStartInfo("powershell.exe",
            "-NoProfile -ExecutionPolicy Bypass -File \"" + script + "\"")
        {
            UseShellExecute = true,
            WorkingDirectory = Path.Combine(root, "mp-studio"),
            WindowStyle = firstRun ? ProcessWindowStyle.Normal : ProcessWindowStyle.Minimized,
        };
        Process.Start(psi);
        return 0;
    }
}
