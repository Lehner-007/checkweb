# 1.2.0

- Neue Programmeinträge im Log verwenden die gewählte Sprache und folgen einem gespeicherten Sprachwechsel sofort; vorhandene Einträge bleiben erhalten.
- Sprache der Oberfläche direkt beim Speichern wechseln, ohne Neustart.
- Menüs, Prüfkategorien, Ergebnisse und Leserichtung aktualisieren; Eingabe, Filter und Befunde erhalten.
- Hilfe und Sprachpakete auf sofortige Umschaltung abgestimmt.

# 1.1.2

- Einheitliche ausgeschriebene Namen installierter Sprachen.
- Herunterladbare Sprachen aus dem GitHub-Katalog auswählen, statt Codes einzugeben.
- Geöffnete Sprachauswahl nach Import oder Download sofort aktualisieren.

# 1.1.1

- Öffentliche GitHub-Links für Versionsprüfung und Sprachpakete ergänzt.
- Alte leere Quellen migrieren; eigene URLs und deaktivierte automatische Prüfung erhalten.
- DEB-Baudateien in GitHub-Quellumfang aufnehmen; lokale Fehlerliste ausschließen.
- DEB-Zwischenstände im Projekt-Ausgabeordner statt im System-Temp-Verzeichnis.

# Änderungen

## 1.1.0 – 28.09.2026

MINOR: neue, getrennte Entwicklungs-/Veröffentlichungsfunktion.

- `erstellegithub.sh` erstellt einen geprüften GitHub-Quellstand, ohne Quelldateien zu verändern.
- `.gitignore`, Pflichtdatei-, Versions-, Geheimnis-, Index- und Historienprüfung.
- Optionaler Veröffentlichungsmodus mit ausdrücklicher Bestätigung, Commit, geschütztem Versionstag und atomarem Push.
- Isolierte Tests für Vorbereitung, Ablehnung und Veröffentlichung an ein lokales Test-Remote.
- Benutzerpaketierung durch `erstellezip.sh` bleibt unverändert.

## 1.0.2 – 28.09.2026

PATCH: Schutz bestehender Sprachimporte und Versionsprüfungen gegen versehentlich verwendete Fremdprojekte.

- Gemeinsame Programmkennung `program_id: checkweb` vor jeder Übernahme prüfen.
- Fehlende oder abweichende Kennungen bei lokalen Importen und GitHub-Downloads ablehnen; installierte Sprachen erhalten.
- Versionsdateien vor Anzeige und Speicherung der erfolgreichen Prüfung validieren.
- Fehlermeldung in allen zehn Sprachen; Hilfen und acht Sprachpakete aktualisiert (273 Texte pro Sprache).
- Vorbereitete Versionsdatei unter `github/version.json`.

## 1.0.1 – 28.09.2026

PATCH auf Grundlage von 1.0.0: bestehende Oberfläche und Sprachressourcen korrigiert und vervollständigt.

- Versionsanzeige im Fenstertitel; zentrale Versionsquelle `VERSION` für Oberfläche, CLI, Berichte und Netzwerkanfragen.
- Doppelte Buttons für Werkzeuge, Einstellungen und Hilfe entfernt; Menüzugänge erhalten.
- Entwicklungs-Prüfeinstellungen auf 100 Seiten, Tiefe 3, 300 Ressourcen und 10 Sekunden zurückgesetzt; 0 bleibt unbegrenzt.
- Gewünschtes checkweb-Bild im Über-Dialog.
- DE/EN-Hilfe aktualisiert; acht getrennte Zusatzsprachpakete mit jeweils 272 Oberflächentexten und vollständiger Bedienhilfe.
- Werkzeugbeschriftung übersetzt und arabische HTML-Berichte auf Rechts-nach-links-Darstellung angepasst.
- HTTP-Bewertungen in den älteren Übersetzungen an manuelle bzw. unbestimmte Ergebnisse angepasst.

Die Zusatzsprachen sind technisch geprüft; eine unabhängige muttersprachliche Prüfung steht aus. GitHub-Veröffentlichung und Downloadquelle sind noch nicht eingerichtet.

### DEB-Paketkorrektur zu 1.1.0 (Programmversion auf Benutzerwunsch unverändert)

- html5lib als Pflichtabhängigkeit; reproduzierbarer DEB-Bau mit erstelledeb.sh.
- Desktop-Verknüpfung beim Installieren und vollständige Entfernung der programmspezifischen Benutzerdaten beim Deinstallieren.
- Upgrade erhält Einstellungen; isolierte Regressionstests für die Paketverwaltung ergänzt.

### Weitere Korrekturen zu 1.1.0 auf Benutzerwunsch

- Start und Beendigung einschließlich Zeitpunkt, Grund, Exit-Code und Laufzeit protokollieren.
- Direkter Symbolpfad im Menü- und Desktop-Eintrag gegen fehlende Icon-Cache-Auflösung.
