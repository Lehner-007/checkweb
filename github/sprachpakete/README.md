# checkweb 1.1.2 – zusätzliche Sprachen und Hilfe

Diese acht Pakete ergänzen das Basispaket (Deutsch/Englisch):

| Datei | Sprache |
|---|---|
| ar.json | Arabisch, Schreibrichtung rechts nach links |
| es.json | Spanisch |
| fr.json | Französisch |
| hi.json | Hindi |
| pt.json | Portugiesisch |
| ru.json | Russisch |
| tr.json | Türkisch |
| zh.json | Vereinfachtes Chinesisch |

Jedes JSON enthält 273 Oberflächentexte und zwölf Abschnitte lokaler HTML-Hilfe.
Die Hilfen beschreiben Start, Prüfungen, Werkzeuge, Standardwerte und 0-Limits,
Netzwerk, HTTP-Bewertung, Ressourcenzählung, dynamische Inhalte, Berichte,
Sprachimport, Versionsprüfung und Protokolleditor.

## Import

1. checkweb öffnen → Optionen → Einstellungen.
2. „Eigene Sprache importieren“ wählen und die gewünschte JSON-Datei auswählen.
3. Sprache auswählen, Einstellungen speichern und Programm neu starten.
4. Hilfe → Bedienungsanleitung öffnet die lokale Hilfe dieser Sprache.

Bestehende Sprachpakete werden vom Programm nicht überschrieben. Ist derselbe
Sprachcode bereits installiert, vor einem Austausch eigene Änderungen sichern;
das Programm lehnt den doppelten Import ab. Die Pakete dieses Archivs installieren
sich nicht automatisch und verändern keine Benutzerkonfiguration.

## Vorbereitung für GitHub

Die acht JSON-Dateien können gemeinsam in einem separaten Verzeichnis des
künftigen Repositorys veröffentlicht werden. Die direkte HTTPS-GitHub-URL dieses
Verzeichnisses wird danach als Sprachquelle eingetragen. Das Programm ergänzt
`/<sprachcode>.json`. Voreingestellte Quelle: `https://raw.githubusercontent.com/Lehner-007/checkweb/main/github/sprachpakete`; lokaler
Import funktioniert ohne GitHub. Dieses Archiv wurde noch nicht hochgeladen.

## Prüfung und Lizenz

Stand: 28.09.2026, passend zu checkweb 1.1.2. Vollständige Schlüssel und Platzhalter,
Import, Schutz bestehender Pakete, Hilfezuordnung, Berichtsausgabe und GUI wurden
technisch geprüft. Arabische Hilfe und HTML-Berichte verwenden `dir="rtl"`.
Technische Ausgaben externer Prüfwerkzeuge bleiben in deren Originalsprache.
Eine unabhängige muttersprachliche Prüfung der Übersetzungen steht aus.

GPL-3.0-only, Copyright 2026 Josef. Vollständiger Lizenztext: LICENSE.

## Programmkennung

Sprachpakete und Versionsdateien müssen auf oberster JSON-Ebene "program_id": "checkweb" enthalten. Fehlende oder fremde Kennungen werden vor der Übernahme abgelehnt. Ältere Pakete ohne Kennung müssen vor einem erneuten Import entsprechend ergänzt werden; bereits installierte Sprachen bleiben erhalten. Die Kennung dient der Projektzuordnung, nicht als Echtheitsnachweis.
