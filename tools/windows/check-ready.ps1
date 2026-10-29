<#
.SYNOPSIS
    Checks whether this Windows PC is ready for Tamarack OS, and which edition it needs.

.DESCRIPTION
    Read-only: it looks at the firmware, Secure Boot, memory, graphics, disks, BitLocker and
    Fast Startup, changes nothing and sends nothing anywhere. Works without administrator
    rights (a few details are more precise as administrator).

    Run it from the folder you saved it in:
        powershell -ExecutionPolicy Bypass -File .\check-ready.ps1

.PARAMETER GpuName
    Only print the edition for these graphics card names (used by the tests).
#>
param(
    [string[]]$GpuName
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$Registry = 'ghcr.io/brecken321'
$Editions = @{
    'main'          = @{ Name = 'Standard'; Image = 'tamarack-os' }
    'nvidia'        = @{ Name = 'NVIDIA'; Image = 'tamarack-os-nvidia' }
    'nvidia-legacy' = @{ Name = 'NVIDIA (older cards)'; Image = 'tamarack-os-nvidia-legacy' }
}

# Edition for a set of graphics card names. NVIDIA GTX 16, RTX and MX 400+ (Turing or newer)
# use the open NVIDIA driver; GTX 750/900/1000, MX 100-300 and Quadro M/P/K620-K2200 (Maxwell, Pascal) need
# the older closed one; Kepler and older are not supported by either and use the standard
# edition's open-source driver.
function Get-TamarackEdition([string[]]$Names) {
    $nvidia = @($Names | Where-Object { $_ -match 'NVIDIA|GeForce|Quadro|Tesla|TITAN' })
    if ($nvidia.Count -eq 0) {
        return @{ Edition = 'main'; Note = '' }
    }
    $card = $nvidia[0]
    if ($card -match 'RTX|GTX\s*16\d\d|MX\s*[4-9]\d\d|Quadro\s+T\d|\bT\d{3,4}\b|\b[AL]\d{1,2}\b|TITAN\s+(RTX|V)') {
        return @{ Edition = 'nvidia'; Note = "$card is Turing or newer." }
    }
    if ($card -match 'GTX\s*(7[45][05]|9\d\d|10\d\d)|GT\s*10\d\d|MX\s*[1-3]\d\d|\b9[2-4]0MX?\b|Quadro\s+([MP]\d|K(620|1200|2200))|TITAN\s*(X|Xp)') {
        return @{ Edition = 'nvidia-legacy'; Note = "$card is Maxwell or Pascal: it needs NVIDIA's older driver." }
    }
    if ($card -match 'GTX\s*[4-7]\d\d|GT\s*[4-7]\d\d|GTX\s*TITAN\b|Quadro\s+K\d') {
        return @{ Edition = 'main'; Note = "$card is too old for NVIDIA's current drivers; the Standard edition uses the open-source driver (fine for the desktop, slow for games)." }
    }
    return @{ Edition = 'nvidia'; Note = "Could not tell the generation of $card; most NVIDIA cards from 2018 on use the NVIDIA edition. Check docs/HARDWARE.md." }
}

if ($GpuName) {
    foreach ($name in $GpuName) {
        $result = Get-TamarackEdition @($name)
        "{0} => {1}" -f $name, $result.Edition
    }
    return
}

$script:Warnings = 0
$script:Failures = 0
function Write-Result([string]$Status, [string]$Message, [string]$Advice = '') {
    $colors = @{ 'OK' = 'Green'; 'WARN' = 'Yellow'; 'FAIL' = 'Red'; 'INFO' = 'Cyan' }
    if ($Status -eq 'WARN') { $script:Warnings++ }
    if ($Status -eq 'FAIL') { $script:Failures++ }
    Write-Host ('[{0,-4}] ' -f $Status) -ForegroundColor $colors[$Status] -NoNewline
    Write-Host $Message
    if ($Advice) { Write-Host ('       ' + $Advice) -ForegroundColor DarkGray }
}
function Get-Safely([scriptblock]$Block) {
    try { & $Block } catch { $null }
}
function Format-GB([double]$Bytes) { '{0:N1} GB' -f ($Bytes / 1GB) }

Write-Host ''
Write-Host 'Tamarack OS readiness check (read-only)' -ForegroundColor White
Write-Host ''

# The computer
$system = Get-Safely { Get-CimInstance Win32_ComputerSystem }
$os = Get-Safely { Get-CimInstance Win32_OperatingSystem }
if ($system) { Write-Result 'INFO' ("{0} {1}" -f $system.Manufacturer.Trim(), $system.Model.Trim()) }
if ($os) { Write-Result 'INFO' ("{0} (build {1})" -f $os.Caption, $os.BuildNumber) }

$cpu = Get-Safely { Get-CimInstance Win32_Processor | Select-Object -First 1 }
if ($cpu) {
    if ($cpu.Architecture -eq 9) {
        Write-Result 'OK' ("64-bit processor: {0}" -f $cpu.Name.Trim())
    } else {
        Write-Result 'FAIL' ("Processor is not 64-bit x86: {0}" -f $cpu.Name.Trim()) 'Tamarack OS needs a 64-bit Intel or AMD processor.'
    }
}

# Firmware and Secure Boot
$firmware = Get-Safely {
    Add-Type -Namespace Tamarack -Name Firmware -MemberDefinition '[DllImport("kernel32.dll")] public static extern bool GetFirmwareType(ref uint FirmwareType);'
    [uint32]$type = 0
    $null = [Tamarack.Firmware]::GetFirmwareType([ref]$type)
    $type
}
switch ($firmware) {
    2 { Write-Result 'OK' 'UEFI firmware' }
    1 { Write-Result 'FAIL' 'Legacy BIOS boot' 'Tamarack OS needs UEFI. Most PCs from 2012 on can switch to UEFI in the firmware setup; Windows may need converting first (mbr2gpt).' }
    default { Write-Result 'WARN' 'Could not tell whether the PC starts in UEFI mode' }
}

$secureBoot = Get-Safely { (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\SecureBoot\State').UEFISecureBootEnabled }
if ($secureBoot -eq 1) {
    Write-Result 'INFO' 'Secure Boot is on' 'Installer: leave it on and enroll the key after installing (password universalblue). Live USB: turn it off while you use it (docs/INSTALL.md).'
} elseif ($secureBoot -eq 0) {
    Write-Result 'INFO' 'Secure Boot is off' 'Both the installer and the live USB start as is.'
}

# Memory
if ($system) {
    $ram = [double]$system.TotalPhysicalMemory
    if ($ram -ge 15GB) {
        Write-Result 'OK' ("Memory: {0}" -f (Format-GB $ram))
    } elseif ($ram -ge 7GB) {
        Write-Result 'OK' ("Memory: {0}" -f (Format-GB $ram)) '16 GB is recommended for recent games. In the live USB, keep to small apps (they download into memory).'
    } elseif ($ram -ge 3.5GB) {
        Write-Result 'WARN' ("Memory: {0}" -f (Format-GB $ram)) 'Enough for the desktop; games will be limited.'
    } else {
        Write-Result 'FAIL' ("Memory: {0}" -f (Format-GB $ram)) 'Tamarack OS needs at least 4 GB.'
    }
}

# Graphics and edition
$gpus = @(Get-Safely { Get-CimInstance Win32_VideoController } | Where-Object { $_ -and $_.Name } | ForEach-Object { $_.Name.Trim() })
foreach ($gpu in $gpus) { Write-Result 'INFO' "Graphics: $gpu" }
$pick = Get-TamarackEdition $gpus
$edition = $Editions[$pick.Edition]
if ($gpus.Count -gt 1 -and $pick.Edition -ne 'main') {
    Write-Result 'INFO' 'Hybrid graphics (integrated + NVIDIA)' 'Normal on laptops: the desktop runs on the integrated chip, games on the NVIDIA card. Tamarack Center > Gaming can start Steam on the NVIDIA card.'
}
Write-Result 'OK' ("Edition: {0} ({1}/{2}:stable)" -f $edition.Name, $Registry, $edition.Image) $pick.Note

# Disks and free space
$disks = @(Get-Safely { Get-CimInstance Win32_DiskDrive } | Where-Object { $_ -and $_.MediaType -match 'Fixed' })
foreach ($disk in $disks) {
    Write-Result 'INFO' ("Disk {0}: {1}, {2}" -f $disk.Index, $disk.Model.Trim(), (Format-GB $disk.Size))
}
if ($disks.Count -gt 1) {
    Write-Result 'INFO' 'More than one internal disk' 'Installing on a disk Windows does not use is the safest way to keep both systems.'
}
$gpt = @(Get-Safely { Get-CimInstance Win32_DiskPartition } | Where-Object { $_ -and $_.Type -like 'GPT*' })
if ($gpt.Count -gt 0) { Write-Result 'OK' 'GPT partition table' }

$volumes = @(Get-Safely { Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' } | Where-Object { $_ })
$best = $null
foreach ($volume in $volumes) {
    if (-not $best -or $volume.FreeSpace -gt $best.FreeSpace) { $best = $volume }
}
if ($best -and $best.FreeSpace -ge 8GB) {
    Write-Result 'OK' ("Room to download an ISO (about 6.5 GB): {0} has {1} free" -f $best.DeviceID, (Format-GB $best.FreeSpace))
} elseif ($best) {
    Write-Result 'WARN' ("Not enough room to download an ISO (about 6.5 GB): the most free space is {0} on {1}" -f (Format-GB $best.FreeSpace), $best.DeviceID) 'Free up space, use another drive, or download it on another PC. The USB stick itself cannot hold the download and be written at the same time.'
}
$systemDrive = $volumes | Where-Object { $_.DeviceID -eq $env:SystemDrive } | Select-Object -First 1
if ($systemDrive) {
    if ($systemDrive.FreeSpace -ge 140GB) {
        Write-Result 'OK' ("Dual-boot on the Windows disk: {0} has {1} free (128 GB or more can be shrunk off)" -f $systemDrive.DeviceID, (Format-GB $systemDrive.FreeSpace))
    } else {
        Write-Result 'WARN' ("Dual-boot on the Windows disk: {0} has only {1} free; 128 GB is recommended for Tamarack OS" -f $systemDrive.DeviceID, (Format-GB $systemDrive.FreeSpace)) 'Free up space first, use a second disk, or replace Windows entirely (back up first).'
    }
}

# Windows settings that matter for installing
$bitlocker = Get-Safely { (New-Object -ComObject Shell.Application).NameSpace($env:SystemDrive).Self.ExtendedProperty('System.Volume.BitLockerProtection') }
if ($bitlocker -in 1, 3, 5, 6) {
    Write-Result 'WARN' ("BitLocker / Device Encryption is on for {0}" -f $env:SystemDrive) 'Save the recovery key before changing firmware settings: account.microsoft.com/devices/recoverykey, or run "manage-bde -protectors -get C:" as administrator.'
} elseif ($bitlocker -in 0, 2) {
    Write-Result 'OK' ("{0} is not encrypted (BitLocker / Device Encryption off)" -f $env:SystemDrive)
}

$fastStartup = Get-Safely { (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power').HiberbootEnabled }
if ($fastStartup -eq 1) {
    Write-Result 'WARN' 'Fast Startup is on' 'For dual-boot, turn it off: Control Panel > Power Options > Choose what the power buttons do.'
} elseif ($fastStartup -eq 0) {
    Write-Result 'OK' 'Fast Startup is off'
}

# Network and battery
$adapters = @(Get-Safely { Get-NetAdapter -Physical } | Where-Object { $_ })
foreach ($adapter in $adapters) {
    Write-Result 'INFO' ("Network: {0}" -f $adapter.InterfaceDescription)
}
$battery = Get-Safely { Get-CimInstance Win32_Battery | Select-Object -First 1 }
if ($battery) {
    Write-Result 'INFO' 'Laptop with a battery' 'Plug in the charger before installing.'
}

Write-Host ''
if ($script:Failures -gt 0) {
    Write-Host ("Not ready: {0} problem(s) above must be fixed first." -f $script:Failures) -ForegroundColor Red
} elseif ($script:Warnings -gt 0) {
    Write-Host ("Ready, with {0} thing(s) to take care of first (see above)." -f $script:Warnings) -ForegroundColor Yellow
} else {
    Write-Host 'Ready.' -ForegroundColor Green
}
Write-Host ("Download: the {0} ISOs ({1}-iso and {1}-live-iso). Guide: docs/INSTALL.md" -f $edition.Name, $edition.Image)
Write-Host ''
