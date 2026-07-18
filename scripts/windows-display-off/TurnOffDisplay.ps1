$source = @'
using System;
using System.Runtime.InteropServices;

public static class DisplayOffNativeMethods
{
    [StructLayout(LayoutKind.Sequential)]
    public struct LASTINPUTINFO
    {
        public uint cbSize;
        public uint dwTime;
    }

    [DllImport("user32.dll")]
    public static extern IntPtr SendMessage(
        IntPtr hWnd,
        uint message,
        IntPtr wParam,
        IntPtr lParam
    );

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool GetLastInputInfo(ref LASTINPUTINFO lastInputInfo);

    [DllImport("kernel32.dll")]
    public static extern uint SetThreadExecutionState(uint executionState);
}
'@

Add-Type -TypeDefinition $source

$hWndBroadcast = [IntPtr]0xffff
$wmSysCommand = 0x0112
$scMonitorPower = [IntPtr]0xF170
$monitorPowerOff = [IntPtr]2
$esContinuous = [uint32]0x80000000
$esSystemRequired = [uint32]0x00000001

function Get-LastInputTick {
    $lastInput = New-Object DisplayOffNativeMethods+LASTINPUTINFO
    $lastInput.cbSize = [Runtime.InteropServices.Marshal]::SizeOf($lastInput)

    if (-not [DisplayOffNativeMethods]::GetLastInputInfo([ref]$lastInput)) {
        throw "Unable to read the last keyboard or mouse input time."
    }

    return $lastInput.dwTime
}

$initialInputTick = Get-LastInputTick

try {
    # Keep Windows awake while the monitor is off. This does not change the
    # user's persistent power-plan settings.
    $result = [DisplayOffNativeMethods]::SetThreadExecutionState(
        $esContinuous -bor $esSystemRequired
    )

    if ($result -eq 0) {
        throw "Unable to temporarily prevent Windows from sleeping."
    }

    [DisplayOffNativeMethods]::SendMessage(
        $hWndBroadcast,
        $wmSysCommand,
        $scMonitorPower,
        $monitorPowerOff
    ) | Out-Null

    # Mouse or keyboard activity wakes the monitor normally. Exit afterward so
    # Windows immediately returns to its original sleep policy.
    while ((Get-LastInputTick) -eq $initialInputTick) {
        Start-Sleep -Milliseconds 500
    }
}
finally {
    [DisplayOffNativeMethods]::SetThreadExecutionState($esContinuous) | Out-Null
}
