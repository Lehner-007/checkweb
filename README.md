# checkweb

Aktuelle Version: **1.3.0**. Die zentrale Versionsquelle ist `VERSION`.

GTK-4-Anwendung zur lokalen und Online-Prüfung von Webseiten. Entwicklung für Linux Mint/Cinnamon. GPL-3.0-only, Copyright 2026 Josef. Vollständiger Lizenztext: LICENSE.

## Start

Im Entwicklungsordner `./start.sh` starten. Das Skript nutzt eine vorhandene projektinterne `.venv`, andernfalls `/usr/bin/python3`. Es installiert keine Pakete. Direkter Start: `python3 checkweb.py`.

Systemabhängigkeiten: `python3-gi`, `gir1.2-gtk-4.0`, `python3-bs4`, `python3-requests`. Für alle unterstützten Checks außerdem `python3-html5lib`, `python3-tinycss2`, `python3-lxml`, `python3-pil`, `php-cli`, `nodejs`. Die App erkennt fehlende optionale Werkzeuge. In der Entwicklungs-VM ist html5lib in `.venv` installiert; die übrigen Python-Bibliotheken werden aus den Systempaketen verwendet.

Nicht-grafische Prüfung: `python3 checkweb.py --local /pfad/zum/projekt --no-network --output bericht.html`. Online: `python3 checkweb.py --url https://example.org --output bericht.json`. `--checks html,links` begrenzt Kategorien; `--tools`, `--version`, `--help` sind verfügbar. Exit-Code 0: Prüflauf beendet ohne Fehlerbefund, 1: Fehlerbefunde, 2: Prüflauf fehlgeschlagen oder unvollständig. Warnungen, Grenzen und nicht ausgeführte Prüfungen trotzdem im Bericht beachten.

## Umfang

HTML5-Struktur, CSS-Parsing, JavaScript/PHP-Syntax, JSON/XML/SVG, Links, Pfade, Bilder, Metadaten, Überschriften, Codierung, grundlegende automatische Barrierefreiheit sowie passive Sicherheits- und Performancemerkmale. Lokaler Quellcode wird nicht ausgeführt. Im Online-Modus wird JavaScript nicht gerendert; dynamische Inhalte und serverseitiger PHP-Code sind dort nicht prüfbar. CSS-Parsing ist keine vollständige Prüfung aller Eigenschaftswerte. Keine vollständige Sicherheits- oder WCAG-Konformitätsprüfung.

Standardgrenzen: 100 Seiten, Linktiefe 3, 300 Dateien/HTTP-Anfragen und 10 Sekunden je Anfrage/Werkzeug. 0 hebt die jeweilige Grenze auf. Die Größenbegrenzung je Ressource bleibt bestehen. Externe Linkprüfung bei lokalen Scans verursacht Netzverkehr, sofern sie eingeschaltet ist. Keine Übermittlung von Quelltexten an externe Prüfdienste. Bei Online-Weiterleitung auf einen anderen Origin wird dieser gemeldet; die Zieladresse lässt sich als neuer Prüfstart verwenden.

## Sprachen

DE/EN und lokale HTML-Hilfe liegen unter lang/ und help/. Eigene JSON-Pakete importieren: `{"program_id":"checkweb","code":"fr","strings":{"start":"Démarrer"},"help_html":"<h1>Aide</h1><p>…</p>"}`. Fehlende Schlüssel fallen auf Englisch zurück; Platzhalter müssen übereinstimmen. Eigenes HTML wird auf passive Inhalte begrenzt. Vorhandene Sprachpakete werden nicht überschrieben.

Interne Downloadquelle: direkte HTTPS-GitHub-Basisadresse, aus der `<code>.json` geladen wird. Voreingestellt ist `https://raw.githubusercontent.com/Lehner-007/checkweb/main/github/sprachpakete`. Die interne Versionsquelle liefert `{"program_id":"checkweb","version":"1.3.0"}`. Es werden keine Updates installiert. Monatsintervalle entsprechen 30 Tagen.

## Prüfen

`.venv/bin/python -m unittest discover -s tests -v` führt isolierte lokale Tests und Tests gegen einen lokalen HTTP-Testserver durch. GUI-Smoke-Test separat unter einer grafischen Sitzung ausführen.

## Werkzeuggrundlagen

- [PHP – CLI-Optionen](https://www.php.net/features.commandline.options.php): Syntaxprüfung mit `-l`, ohne Ausführung; `-n` ignoriert php.ini.
- [Node.js – Kommandozeile](https://nodejs.org/docs/latest-v18.x/api/cli.html): `--check` prüft Syntax, ohne das Skript auszuführen.
- [tinycss2 – API](https://doc.courtbouillon.org/tinycss2/stable/api_reference.html): CSS-Parser mit ParseError-Diagnosen.

Externe Bibliotheken werden nicht mit dem Programm kopiert, sondern als getrennte Abhängigkeiten verwendet. PyGObject: LGPL; Beautiful Soup: MIT; requests: Apache-2.0; html5lib/tinycss2: MIT; lxml: BSD; Pillow: HPND. PHP/Node werden als separate installierte Programme aufgerufen. Bei Änderungen am Distributionsumfang die Lizenzen erneut prüfen.

## Bedienkorrekturen

Menüzeile mit Datei, Prüfungen und Hilfe. Online-Adressen ohne Protokoll erhalten `https://`. Dateidialoge werden bis zum Abschluss gehalten und mit vorhandenem Startordner geöffnet. Berichtsexport ergänzt fehlende Endungen entsprechend HTML/JSON. Fehlende Werkzeuge erscheinen im Hauptfenster und im Log.

## HTTP-Bewertung und Berichte

HTTP 404/410 werden als bestätigte Linkfehler laut Zielserver hervorgehoben. HTTP 401/403,
429, 5xx und Zeitüberschreitungen erfordern eine manuelle oder spätere Prüfung;
sie belegen keinen dauerhaft defekten Link. Normale Weiterleitungen bleiben
Hinweise. Durch robots.txt ausgeschlossene Ziele erscheinen als nicht geprüft.
Eine nicht abrufbare robots.txt wird von einem ausdrücklichen Abrufverbot getrennt.

HTML-Berichte enthalten Zusammenfassung, Fehler, Warnungen, manuell zu prüfende
Ergebnisse, Hinweise/Optimierungen, nicht geprüfte Bereiche, Weiterleitungen und
technische Details. Gleichartige Befunde werden gruppiert; alle Fundstellen sind
aufklappbar. In der Oberfläche öffnet die Auswahl einer Gruppe deren Fundstellen.
JSON behält sämtliche Einzelfunde und enthält zusätzlich `limits`.
Erreichte Ressourcen- oder Seitenlimits setzen den Status auf `incomplete`
(„Prüfung unvollständig“) und erzeugen je Grenze nur einen Hinweis. Ein beendeter
Lauf ohne erreichte Grenze kann trotzdem nicht geprüfte Ziele enthalten.

Zusätzliche GUI-Prüfung: `.venv/bin/python tests/gui_reports.py`.

HTML-Berichte verwenden `assets/report_watermark.png` als dezentes Wasserzeichen (5 % Deckkraft). Das Bild wird direkt in die HTML-Datei eingebettet und benötigt beim Öffnen keine externe Datei oder Netzwerkverbindung.

Im Ergebnisbereich des Programmfensters erscheint dasselbe Logo bereits vor der ersten Prüfung mit 10 % Deckkraft. Es liegt hinter der bedienbaren Ergebnisliste und passt sich deren Größe an.

Auch die lokale deutsche und englische Hilfe zeigt das Logo mit 10 % Deckkraft im Hintergrund.

Die Einstellungen haben eine feste Fußzeile mit Abbrechen und Einstellungen speichern. Das Versionsprüfintervall wird als Zahl mit Tage/Wochen/Monate gemeinsam eingegeben (Monat = 30 Tage). Das Hilfe-Menü enthält Bedienungsanleitung und Über checkweb. GUI-Regression: `.venv/bin/python tests/gui_settings.py`.

## Nachvollziehbare Prüfübersicht

Die Eingabe für URL/Ordner besitzt „Eingabe löschen“; während einer Prüfung ist
diese Aktion gesperrt. Der Bericht enthält Ziel, Prüfart, Status, Start/Ende im
Format DD.MM.YYYY mit Uhrzeit und Zeitzone sowie die tatsächlich gemessene Dauer.

Ressourcen zählen eindeutige bekannte Dateipfade oder normalisierte URLs ohne
Fragment. `found = checked + unchecked`. Abschließend geprüft heißt: die geplanten
Inhalts-/Linkschritte sind abgeschlossen oder HTTP 404/410 wurde festgestellt.
Nicht vollständig geprüft umfasst auch Teilergebnisse und unbestimmte Antworten.
Angefangene Inhaltsauswertungen und HTTP-Anfragen (einschließlich robots.txt,
Weiterleitungen und Wiederholungen) werden separat gezählt. Nicht entdeckte Teile
der Webseite werden nicht geschätzt. JSON enthält diese Mengen unter
`resource_counts` sowie die prüfbaren Einzelzustände unter `resource_details`.

Interne Online-Ziele haben denselben Hostnamen wie das Prüfziel; Protokoll oder
Port ändern diese Zuordnung nicht. Andere Hostnamen sind extern. Lokal gehören
Pfade innerhalb der Projektwurzel zu intern, Webziele zu extern. Externe Befunde
sind keine pauschale Aussage über den technischen Zustand der geprüften Webseite.

Die Ergebnisgruppen zählen jeweils Einzelfundstellen, keine Ressourcen. Fehler
zeigen Fundseite, Zieladresse, Zeile und HTTP-Status offen an. Ressourcen-, Seiten-
und Tiefengrenzen sowie offene Ziele oder fehlgeschlagene Werkzeugprüfungen führen
zu „Prüfung unvollständig“. Der Kommandozeilenstart liefert dafür Exit-Code 2.
Die Berichtsvorgabe liegt unter `docs/pruefbericht_vorgabe.dm`.


## Manuelle Kontrollprüfung: Bewertung, Ressourcen und Log

Eigene Fehler und externe Fehler stehen in getrennten Gruppen. 401/403 erfordern
manuelle Kontrolle; Timeout, Netzwerkfehler, 429, 5xx und robots.txt gelten als
nicht automatisch bestimmbar. Diese Befunde zählen nicht als bestätigte Fehler.
Ein eindeutiges 404/410 bleibt ein Linkfehler, mit Quelle, Zeile, Linktext und Ziel.
Fehlende interne Dateien zählen als Fehler und stehen vor externen Linkfehlern.

`resource_details` enthält zusätzlich Typ, HTTP-Status und referenzierende Quellen.
HTML-Berichte stellen HTML, CSS, JavaScript, Bilder, Schriften und XHR/Fetch getrennt
dar. Verschachtelte CSS-Ressourcen werden relativ zum jeweiligen Stylesheet
aufgelöst; Fetch-URLs relativ zur einbindenden Seite. Die konservative statische
Erkennung unterstützt `fetch('URL')` ohne Optionen und XHR `open('GET', 'URL')`
beziehungsweise HEAD. Dynamische Ausdrücke benötigen Browserkontrolle. Es werden
keine Browserkonsole und keine anderen Tabs eingelesen, keine Skripte ausgeführt
und keine POST-Aufrufe vorgenommen.

Die vier Scan-Grenzen unterstützen 0 = unbegrenzt, einschließlich Linktiefe.
Positive Werte und neutrale Defaults bleiben erhalten. Größenbegrenzung je Datei,
robots.txt und Origin-Regeln gelten weiter. GUI-Scans mit Zeitlimit 0 laufen in
einem separaten Python-Prozess, damit Abbrechen auch einen blockierenden
Netzwerkabruf unterbrechen kann und Teilergebnisse verfügbar bleiben.

Hilfe → Protokoll öffnen / bearbeiten bietet einen Editor für das aktive Log.
Speichern schützt zwischenzeitliche Änderungen und erhält das vom Logger geöffnete
Dateiobjekt. Neu laden und das Verwerfen ungespeicherter Änderungen sind explizit.
Anforderungen: `docs/manuelle_kontrolle.dm`; Regressionen: `tests/test_manual_review.py`.

## Benutzerpaket

Das Programm-ZIP enthält DE/EN samt lokaler HTML-Hilfe. Nach dem Entpacken mit `python3 checkweb.py` starten; die oben genannten Systemabhängigkeiten müssen verfügbar sein. `start.sh` ist nur für die Entwicklung und liegt nicht im ZIP. Private Einstellungen, Logs und Testdateien werden nicht ausgeliefert.

Arabisch, Spanisch, Französisch, Hindi, Portugiesisch, Russisch, Türkisch und vereinfachtes Chinesisch stehen als getrennte JSON-Sprachpakete mit vollständiger Hilfe bereit. Im Menü Datei → Einstellungen importieren, Sprache auswählen, speichern; die Oberfläche schaltet sofort um. Bestehende eigene Sprachpakete werden erhalten; ein erneuter Import desselben Sprachcodes wird abgelehnt. Die GitHub-Downloadquelle ist voreingestellt; die Quellen sind fest im Programm hinterlegt.

Der Fenstertitel zeigt die Version. Werkzeuge stehen unter Hilfe → Info, Einstellungen unter Datei mit sichtbaren Trennlinien, die Bedienungsanleitung im Hilfe-Menü. Der Über-Dialog verwendet `assets/checkweb.png`. Siehe `CHANGELOG.md`.

## Programmkennung ab 1.0.2

Sprachpakete und Versionsdateien müssen auf oberster JSON-Ebene "program_id": "checkweb" enthalten. Fehlende oder fremde Kennungen werden vor der Übernahme abgelehnt. Ältere Pakete ohne Kennung müssen vor einem erneuten Import entsprechend ergänzt werden; bereits installierte Sprachen bleiben erhalten. Die Kennung dient der Projektzuordnung, nicht als Echtheitsnachweis.

Die vorbereitete Versionsdatei liegt in `github/version.json`, die Sprachpakete in `github/sprachpakete/`. Für die Versionsprüfung wird die direkte GitHub-URL der Datei verwendet, für Sprachen die direkte URL des Ordners. Ohne gültige Kennung wird weder eine Sprache installiert noch eine Versionsprüfung als erfolgreich gespeichert.

## GitHub-Quellstand vorbereiten

`./erstellegithub.sh` prüft ausschließlich den GitHub-Quellumfang und erzeugt eine neue Kopie unter `dist/checkweb-github-<Version>-<Kennung>/`. Es liest die Version aus `VERSION`, zeigt jede vorgesehene Datei und verändert keine Quelldateien. Jeder Lauf erhält einen eigenen Ausgabeordner. Vorhandene Ausgaben bleiben bestehen.

Enthalten sind Programmcode, Tests, Assets, DE/EN-Hilfe und Oberflächentexte, öffentliche Projektdokumentation, GitHub-Sprachpakete samt Versionsdatei, Lizenz, Versionsinformationen, Start- und Veröffentlichungsskripte und `.gitignore`. Die Struktur bleibt erhalten. Neue unbekannte Dateien müssen zuerst bewusst dem Quellumfang zugeordnet werden; sie werden nicht stillschweigend veröffentlicht.

`.venv`, `__pycache__`, `.config`, `dist`, Logs, Caches und Sicherungsdateien werden ausgeschlossen. `.env`, Schlüsseldateien und erkennbare fest eingetragene Zugangsdaten im untersuchten Quellbereich führen zum Abbruch mit Dateiname und Fehlercode; nichts wird gelöscht. Bereits getrackte Inhalte und erreichbare Git-Historie werden ebenfalls geprüft. Die Musterprüfung erkennt offensichtliche Geheimnisse, ersetzt aber keine manuelle Inhaltsprüfung.

### Bewusst veröffentlichen

Die lokale Vorbereitung benötigt kein Git-Repository. Für einen tatsächlichen Push zuerst ein Git-Repository im Projektordner sowie einen Branch, eine Git-Autorenidentität und ein Remote zum gewünschten öffentlichen GitHub-Repository einrichten. Das Skript legt weder Repository noch Remote automatisch an. Die tatsächliche Sichtbarkeit des GitHub-Repositorys muss bei dessen Einrichtung auf öffentlich gesetzt werden; das Skript ändert diese Einstellung nicht.

`./erstellegithub.sh --publish` prüft den Stand erneut. `--remote NAME` wählt ein anderes Remote als `origin`. Vor Änderungen zeigt das Skript Dateiliste, Repository, Branch, Version, Commit-Meldung und Tag. Erst nach der exakten Eingabe `VERÖFFENTLICHEN <Version>` erstellt es bei Änderungen einen Commit `Release Checkweb <Version>`, den Tag `v<Version>` und überträgt ausschließlich diesen Branch und Tag atomar. Eingabeende, Nein oder eine andere Eingabe bedeutet kein Commit, Tag oder Push. Bestehende lokale oder entfernte Tags werden niemals überschrieben. Kein Force-Push. Git-Hooks sind bei diesen kontrollierten Schritten deaktiviert.

Bei einem Verbindungs- oder Pushfehler können ein lokaler Commit und Tag bereits existieren. Sie bleiben zur Prüfung erhalten; das Skript löscht sie nicht und meldet keinen Veröffentlichungserfolg. Ursache und lokalen Git-Stand vor einem erneuten Versuch prüfen. Eine bereits existierende Versionsmarke führt dann zur ausdrücklichen Ablehnung statt zu einer stillen Wiederveröffentlichung.

`erstellezip.sh` bleibt unverändert für das normale Benutzerpaket zuständig. Das GitHub-Skript wird nicht in das Benutzer-ZIP aufgenommen. Tests des neuen Ablaufs: `python3 -m unittest discover -s tests -p test_github_preparation.py -v`; diese verwenden ausschließlich lokale isolierte Git-Repositories und keine echte GitHub-Verbindung.

## DEB-Paket und vollständige Deinstallation

`./erstelledeb.sh` erstellt das DEB aus der zentralen `VERSION`, ohne die Programmversion zu ändern. Das Paket installiert einen Menüeintrag und auf vorhandenen, aktivierten Benutzer-Desktops eine Checkweb-Verknüpfung. `python3-html5lib` ist eine Pflichtabhängigkeit; die Installation mit APT löst diese auf. Ein bloßer Aufruf von `dpkg -i` lädt fehlende Abhängigkeiten nicht herunter.

Installation: `sudo apt install ./checkweb_1.3.0_all.deb`. Entfernung: `sudo apt remove checkweb`. Bereits beim Entfernen werden Checkwebs persönliche Einstellungen, Profile, Sprachdateien, Hilfen, Logs, Caches und Zustandsdaten in seinen Benutzerordnern gelöscht. Erkannte Checkweb-Verknüpfungen werden ebenfalls entfernt, einschließlich solcher im Benutzer-Papierkorb. Der Entwicklungsordner und unabhängig gespeicherte Berichte bleiben erhalten. Bei einem Upgrade bleiben Benutzerdateien erhalten.

Die Bereinigung läuft mit den Rechten des jeweiligen Benutzers. Nicht erreichbare Benutzerordner und abweichende, bei der Paketverwaltung nicht bekannte XDG-Pfade müssen gegebenenfalls gesondert geprüft werden. Die Desktop-Vertrauensmarkierung wird gesetzt, soweit die Sitzung sie unterstützt; andernfalls kann Cinnamon beim ersten Start eine Bestätigung verlangen.

## Start- und Endprotokoll

Normale GUI- und Prüfläufe protokollieren Start und Ende mit Datum, Uhrzeit, Zeitzone, Version, Prozess-ID, Betriebsart, Beendigungsgrund, Exit-Code und Laufzeit. Fehler, Strg+C und SIGTERM werden unterschieden. Reine Informationsaufrufe wie `--version` und `--help` erzeugen keinen Programmlauf. Bei SIGKILL, Stromausfall oder einem harten Prozessabsturz kann kein Ende mehr geschrieben werden; dann fehlt der passende Endeintrag.

## GitHub-Adressen

- Projekt: https://github.com/Lehner-007/checkweb
- Versionsprüfung: https://raw.githubusercontent.com/Lehner-007/checkweb/main/github/version.json
- Sprachpakete: https://raw.githubusercontent.com/Lehner-007/checkweb/main/github/sprachpakete

Leere Quellen aus alten Einstellungen werden beim Laden mit diesen Vorgaben ergänzt. Gespeicherte eigene Quellen werden durch die Projektquellen ersetzt. Prüfung bei jedem Start; eine zusätzliche regelmäßige Prüfung ist optional. Keine automatische Installation.

## Sprachauswahl

Installierte Sprachen erscheinen mit ausgeschriebenen Namen in der gewählten Oberflächensprache. „Sprache und Hilfe nachladen“ lädt auf Benutzeraktion den Katalog `catalog.json` aus der konfigurierten Sprachquelle und bietet noch nicht installierte Sprachen zur Auswahl an. Nach Import oder Download erscheint die neue Sprache sofort in den geöffneten Einstellungen; Auswahl speichern; die Anwendung schaltet ohne Neustart um. Eigene Katalogeinträge und Sprachpakete können einen vollständigen `name` mitführen.

Neue programmgesteuerte Logmeldungen verwenden die eingestellte Sprache, auch nach einem gespeicherten Sprachwechsel. Vorhandene Einträge bleiben unverändert. Technische Fremdmeldungen und Tracebacks bleiben im Original.

## Einheitliche Darstellung

Einstellungen stehen unter Datei zwischen sichtbaren Trennlinien. Die Sprachauswahl steht bei den Sprachpaketen. Start, Abbrechen, Bericht speichern und Prüfauswahl werden über die Menüleiste bedient. Während der Webseitenprüfung zeigt ein zentriertes Fenster den aktuellen Vorgang, Fortschritt und Abbrechen; es schließt nach Abschluss oder Abbruch. Ergebniszeilen wechseln ihre Hintergrundhelligkeit. Neue Protokollsitzungen erhalten sichtbare Trenner und lokale Datumsangaben DD.MM.YYYY HH:MM:SS. Der vorhandene Protokolleditor ist unter Hilfe erreichbar. Die Menühöhe bleibt unverändert. Es werden keine Profile, Demonstrationen, zusätzlichen Exportformate oder Fensterzustandsmodule ergänzt.

## Updates in 1.3.0

Die Software wird bei jedem Start geprüft. In Datei → Einstellungen erscheint Software aktuell, Update verfügbar oder eine Meldung über eine fehlgeschlagene Prüfung. GitHub-Adressen sind interne Vorgaben. Der Download-Button ist nur bei einer neueren Version mit gültigen DEB-Metadaten aktiv. Er lädt in den persönlichen Downloadordner und prüft SHA-256, Paketname, Version und Architektur. Abbruch entfernt die unvollständige Datei; vorhandene andere Dateien werden nicht überschrieben. Installation erfolgt anschließend durch den Anwender.

Die veröffentlichte Versionsdatei benötigt für Downloads zusätzlich `deb` mit `url`, `filename` und `sha256` des tatsächlich erstellten Release-Pakets. Ohne diese Angaben wird kein ungeprüfter Download angeboten. Bei einer Veröffentlichung müssen diese Angaben zum angehängten DEB passen.

Hilfe → Info zeigt erkannte Werkzeuge, Versionen und Paketnamen. Fortschrittsfenster halten vier Textzeilen bereit; längere Meldungen sind scrollbar. Das Bild im Über-Dialog ist auf 128 × 128 Pixel begrenzt.

Nach dem DEB-Bau erzeugt `python3 packaging/prepare_update.py dist/checkweb_1.3.0_all.deb github/version.json` die zugehörigen geprüften Download-Metadaten. Die Release-Automation übernimmt das aus ihrem tatsächlichen DEB und aktualisiert die öffentliche Versionsdatei erst nach erfolgreicher Veröffentlichung.
