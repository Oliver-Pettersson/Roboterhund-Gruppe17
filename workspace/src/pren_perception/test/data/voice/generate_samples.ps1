# Erzeugt Testaufnahmen (16 kHz, 16 Bit, mono) mit der deutschen Windows-Stimme.
# Aufruf: powershell -File generate_samples.ps1
# Ergebnis: commands\*.wav (ein Befehlswort) und background\*.wav (Gespraeche ohne Befehl).

Add-Type -AssemblyName System.Speech
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000,
    [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,
    [System.Speech.AudioFormat.AudioChannel]::Mono)
$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::NotSet, [System.Speech.Synthesis.VoiceAge]::NotSet, 0,
    [System.Globalization.CultureInfo]::GetCultureInfo('de-DE'))

function Save-Speech($folder, $name, $text, $rate) {
    New-Item -ItemType Directory -Force (Join-Path $here $folder) | Out-Null
    $voice.Rate = $rate
    $voice.SetOutputToWaveFile((Join-Path $here "$folder\$name.wav"), $format)
    $voice.Speak($text)
    $voice.SetOutputToNull()
}

$commands = @{ hier = 'Hier!'; brav = 'Brav!'; sitz = 'Sitz!'; such = 'Such!' }
foreach ($word in $commands.Keys) {
    foreach ($rate in -2, 0, 2) {
        Save-Speech 'commands' "${word}_rate$rate" $commands[$word] $rate
    }
}

$background = @(
    'Ich gehe heute Nachmittag noch schnell einkaufen.',
    'Hast du gestern das Spiel im Fernsehen gesehen?',
    'Wir sollten uns morgen um zehn Uhr im Labor treffen.',
    'Kannst du mir bitte das Kabel dort drueben geben?',
    'Ich suche schon seit einer Stunde meinen Schluessel.',
    'Setz dich doch bitte hier auf den Stuhl.',
    'Der Hund sitzt brav neben dem Sofa und schlaeft.',
    'Komm mal hierher und schau dir das an.',
    'Die Praesentation ist am Donnerstag um vierzehn Uhr.',
    'Das Wetter ist heute wirklich schoen.',
    'Ich habe keine Ahnung, wo das Problem liegt.',
    'Wie spaet ist es eigentlich schon?'
)
for ($i = 0; $i -lt $background.Count; $i++) {
    Save-Speech 'background' ('satz_{0:D2}' -f $i) $background[$i] 0
}

# Einzelne Woerter, die kein Befehl sind (aehnlich klingend oder haeufig im Gespraech)
$distractors = @('Ja', 'Nein', 'Okay', 'Danke', 'Hallo', 'Super', 'Genau', 'Bitte',
                 'Sitzen', 'Suchen', 'Hierher', 'Platz', 'Auf', 'Bravo', 'Schatz', 'Fisch')
foreach ($word in $distractors) {
    Save-Speech 'distractors' $word.ToLower() "$word." 0
}
"Fertig: $here"
