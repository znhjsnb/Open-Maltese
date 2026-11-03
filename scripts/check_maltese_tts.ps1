# Read-only diagnostics. No packages are installed and no browser settings change.
param([string]$Word = 'ktieb')
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Write-Output 'Open-Malti: Maltese voice diagnostics'
$engine = Get-Command espeak-ng -ErrorAction SilentlyContinue
if ($engine) {
    Write-Output 'eSpeak-NG Maltese voices:'
    & $engine.Source --voices=mt
    Write-Output 'To hear a sample, run: espeak-ng -v mt "ktieb"'
} else {
    Write-Output 'eSpeak-NG is not on PATH. Official releases: https://github.com/espeak-ng/espeak-ng/releases'
}
try {
    Add-Type -AssemblyName System.Speech
    $tts = New-Object System.Speech.Synthesis.SpeechSynthesizer
    try {
        $voices = @($tts.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo } | Where-Object { $_.Culture.Name -match '^mt(?:-|$)' })
        if ($voices.Count) { $voices | Select-Object Name, Culture | Format-Table }
        else { Write-Output 'No Maltese System.Speech voice is installed.' }
    } finally { $tts.Dispose() }
} catch { Write-Output 'System.Speech voice inventory is unavailable in this PowerShell host.' }
Write-Output 'Browser inventory (paste in browser developer console):'
Write-Output "speechSynthesis.getVoices().filter(v => /^(mt|mlt)(-|$)/i.test(v.lang))"
Write-Output 'If empty, wait for voiceschanged and check again. Edge Read Aloud voices may not be exposed to web pages.'
Write-Output 'Installing a CLI engine alone does not register a browser speechSynthesis voice.'
