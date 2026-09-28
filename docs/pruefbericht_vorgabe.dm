# ============================================================
# CHECKWEB – VERBINDLICHE VORGABE FÜR DEN PRÜFBERICHT
# ============================================================
#
# ZWECK
# -----
# Diese Datei beschreibt die verbindlichen Anforderungen an die
# Auswertung und Darstellung eines checkweb-Prüfberichts.
#
# Ziel ist ein klarer Bericht, in dem echte Fehler sofort erkennbar
# sind und nicht mit Weiterleitungen, Zugriffsbeschränkungen oder
# unvollständigen Prüfungen vermischt werden.
#
# Codex muss diese Vorgaben bei der Weiterentwicklung von checkweb
# berücksichtigen.
#
# Datumsformat: DD.MM.YYYY
#
# ============================================================


# ============================================================
# 1. GRUNDREGELN
# ============================================================
#
# - Ein HTTP-Statuscode darf nicht ohne Kontext bewertet werden.
# - Echte Fehler, unsichere Ergebnisse und reine Hinweise müssen
#   getrennt dargestellt werden.
# - Nicht ausgeführte Prüfungen dürfen niemals als erfolgreich gelten.
# - Eine unvollständige Prüfung muss deutlich als unvollständig
#   gekennzeichnet werden.
# - Gleichartige Ergebnisse sollen zusammengefasst werden.
# - Interne und externe Ziele sollen unterscheidbar sein.
# - Technische Details dürfen die eigentliche Fehlerübersicht nicht
#   überladen.
# - Detailinformationen sollen bei Bedarf aufklappbar sein.


# ============================================================
# 2. REIHENFOLGE DES BERICHTS
# ============================================================
#
# Der Bericht wird in dieser Reihenfolge aufgebaut:
#
# 1. Prüfstatus / Zusammenfassung
# 2. Fehler
# 3. Warnungen
# 4. Manuell zu prüfende Ergebnisse
# 5. Hinweise / Optimierungen
# 6. Nicht geprüfte Bereiche
# 7. Weiterleitungen
# 8. Technische Details


# ============================================================
# 3. PRÜFSTATUS / ZUSAMMENFASSUNG
# ============================================================
#
# Am Anfang des Berichts muss eine kompakte Zusammenfassung stehen.
#
# Darzustellen sind mindestens:
#
# Ziel:
# Prüfart:
# Status:
# Start:
# Ende:
# Dauer:
#
# Ressourcen:
# - gefunden
# - geprüft / ausgewertet
# - nicht geprüft
# - Prüfgrenze
#
# Ergebnisse:
# - Fehler
# - Warnungen
# - manuell zu prüfen
# - Hinweise / Optimierungen
# - nicht geprüft
# - Weiterleitungen
#
# Beispiel:
#
# PRÜFSTATUS
#
# Ziel:             https://example.org/
# Prüfart:          Online
# Status:           UNVOLLSTÄNDIG
# Dauer:            1 min 18 s
#
# Ressourcen:
# Gefunden:         350
# Geprüft:          121
# Nicht geprüft:    229
# Ressourcenlimit:  300
#
# Ergebnisse:
# Fehler:             1
# Warnungen:           0
# Manuell prüfen:      2
# Optimierungen:       6
# Nicht geprüft:       8
# Weiterleitungen:    35
#
# WICHTIG:
# Die Werte müssen eindeutig definiert und rechnerisch nachvollziehbar
# sein. Unterschiedliche Zählweisen dürfen nicht unter derselben
# Bezeichnung dargestellt werden.


# ============================================================
# 4. UNVOLLSTÄNDIGE PRÜFUNG
# ============================================================
#
# Wird eine Prüfgrenze erreicht oder kann ein wesentlicher Teil der
# Prüfung nicht ausgeführt werden, muss deutlich erscheinen:
#
# PRÜFUNG UNVOLLSTÄNDIG
#
# Zusätzlich angeben:
# - welche Grenze erreicht wurde
# - eingestellter Grenzwert
# - wie viele Ressourcen gefunden wurden, sofern bekannt
# - wie viele tatsächlich geprüft wurden
# - wie viele nicht geprüft wurden, sofern bestimmbar
# - Empfehlung für einen erneuten Prüflauf
#
# Beispiel:
#
# PRÜFUNG UNVOLLSTÄNDIG
# Ressourcenlimit erreicht: 300
# Weitere Ressourcen konnten nicht geprüft werden.
# Empfehlung: Ressourcenlimit erhöhen und Prüfung erneut durchführen.
#
# Diese Meldung wird EINMAL zusammenfassend ausgegeben.
# Nicht für jede übersprungene Ressource dieselbe Meldung erzeugen.


# ============================================================
# 5. HTTP-BEWERTUNG
# ============================================================
#
# 200–299
# Status:
#   OK / erreichbar
#
# 300–399
# Status:
#   WEITERLEITUNG
# Bewertung:
#   normalerweise kein Fehler
#
# 401
# Status:
#   MANUELL PRÜFEN
# Bewertung:
#   Anmeldung oder Berechtigung erforderlich
#   nicht automatisch als defekten Link werten
#
# 403
# Status:
#   MANUELL PRÜFEN
# Bewertung:
#   automatisierter Abruf verweigert
#   nicht automatisch als defekten Link werten
#
# Empfohlener Text:
#   Automatisierter Abruf verweigert (HTTP 403).
#   Der Link wird nicht automatisch als defekt bewertet.
#   Im normalen Browser manuell prüfen.
#
# 404 / 410
# Status:
#   FEHLER
# Bewertung:
#   wahrscheinlich defekter oder nicht mehr vorhandener Link
#
# 429
# Status:
#   MANUELL PRÜFEN
# Bewertung:
#   Rate-Limit / zu viele Anfragen
#   Ergebnis nicht eindeutig
#
# 500–599
# Status:
#   MANUELL PRÜFEN
# Bewertung:
#   Serverproblem zum Zeitpunkt der Prüfung
#   nicht automatisch als dauerhaft defekten Link bewerten
#
# Timeout / ReadTimeout
# Status:
#   MANUELL PRÜFEN
# Bewertung:
#   Ergebnis unbestimmt
#   erneute oder manuelle Prüfung empfehlen


# ============================================================
# 6. FEHLERDARSTELLUNG
# ============================================================
#
# Echte Fehler müssen klar und kompakt dargestellt werden.
#
# Wenn vorhanden, anzeigen:
# - Fehlerart
# - HTTP-Status
# - betroffene Zieladresse
# - Fundstelle
# - Datei / Seite
# - Zeilennummer
# - kurze Erklärung
# - konkrete Empfehlung
#
# Beispiel:
#
# FEHLER
#
# HTTP 404 – Ziel wahrscheinlich nicht mehr vorhanden
#
# Gefunden auf:
# software-zentrale.php
#
# Zeile:
# 775
#
# Ziel:
# https://example.org/alte-seite/
#
# Empfehlung:
# Link manuell prüfen und gegebenenfalls korrigieren oder entfernen.


# ============================================================
# 7. INTERNE UND EXTERNE ZIELE
# ============================================================
#
# Der Bericht muss unterscheiden zwischen:
#
# INTERN
# - Ziel gehört zur geprüften Webseite / Domain
#
# EXTERN
# - Ziel gehört zu einer fremden Domain
#
# Ein Fehler einer externen Webseite darf nicht so dargestellt werden,
# als wäre dadurch automatisch die geprüfte Webseite technisch defekt.
#
# Die Fundstelle auf der geprüften Webseite muss trotzdem angegeben
# werden, sofern bekannt.


# ============================================================
# 8. WEITERLEITUNGEN
# ============================================================
#
# Normale Weiterleitungen sind keine Fehler.
#
# Sie werden in einer eigenen Gruppe dargestellt:
#
# WEITERLEITUNGEN
#
# Gleichartige Weiterleitungen zusammenfassen.
#
# Beispiel:
#   32 normale Weiterleitungen
#
# Die vollständige Liste kann aufklappbar dargestellt werden.
#
# Bei einem Wechsel auf einen anderen Origin:
# - als Weiterleitung kennzeichnen
# - nicht automatisch als Linkfehler werten
# - kennt checkweb das Endziel nicht, deutlich angeben:
#   „Endziel nicht geprüft“


# ============================================================
# 9. ROBOTS.TXT
# ============================================================
#
# Verhindert robots.txt den automatisierten Abruf:
#
# Status:
#   NICHT GEPRÜFT
#
# Bewertung:
#   kein Fehler der geprüften Webseite
#
# Empfohlener Text:
#   Automatisierter Abruf gemäß robots.txt nicht erlaubt.
#   Ziel wurde nicht geprüft.
#   Bei Bedarf manuell prüfen.


# ============================================================
# 10. HINWEISE / OPTIMIERUNGEN
# ============================================================
#
# Optimierungsmöglichkeiten dürfen nicht als Fehler erscheinen.
#
# Beispiele:
# - kein Cache-Control-Header
# - keine HTTP-Kompression
# - keine Content-Security-Policy
#
# Die Meldung muss deutlich machen, ob es sich um:
# - Performance-Hinweis
# - Sicherheitshinweis
# - SEO-Hinweis
# - Barrierefreiheits-Hinweis
# - sonstige Optimierung
# handelt.
#
# Das Fehlen einer empfohlenen Sicherheitsmaßnahme darf nicht
# automatisch als nachgewiesene Sicherheitslücke bezeichnet werden.


# ============================================================
# 11. ZÄHLUNGEN
# ============================================================
#
# Alle Zähler müssen eindeutig definiert sein.
#
# Begriffe nicht für unterschiedliche Mengen wiederverwenden.
#
# Beispiel:
#
# NICHT:
#   Nicht geprüft: 8
# und später ohne Erklärung:
#   Nicht geprüft / unbestimmt: 7
#
# BESSER:
#   Nicht geprüfte Befunde: 8
#   davon Links mit unbestimmtem Ergebnis: 7
#
# Falls zwei Werte unterschiedliche Dinge zählen, muss dies direkt
# aus der Beschriftung hervorgehen.


# ============================================================
# 12. PRÜFDAUER
# ============================================================
#
# Zusätzlich zu Start- und Endzeit muss die Dauer verständlich
# dargestellt werden.
#
# Beispiel:
#   Start: 27.09.2026 14:09:08
#   Ende:  27.09.2026 14:10:26
#   Dauer: 1 min 18 s


# ============================================================
# 13. WERKZEUGE
# ============================================================
#
# In der normalen Berichtansicht zunächst nur kompakt anzeigen:
#
# - Werkzeug
# - Version
# - verfügbar / nicht verfügbar
#
# Weitere technische Angaben können aufklappbar dargestellt werden.
#
# Ein nicht verfügbares Werkzeug muss klar gekennzeichnet werden.
# Eine dadurch nicht ausgeführte Prüfung darf nicht als Erfolg zählen.


# ============================================================
# 14. TECHNISCHE DETAILS
# ============================================================
#
# Technische Details gehören ans Ende des Berichts.
#
# Dazu zählen beispielsweise:
# - Prüfoptionen
# - max_pages
# - max_depth
# - max_resources
# - timeout
# - max_bytes
# - delay
# - aktivierte Kategorien
# - verwendete Werkzeuge
# - Werkzeugversionen
# - technische Einzelprotokolle
#
# Diese Informationen sollen die Hauptauswertung nicht überladen.


# ============================================================
# 15. DARSTELLUNG
# ============================================================
#
# Der Bericht muss ohne langes Suchen erkennen lassen:
#
# 1. Ist die Prüfung vollständig?
# 2. Gibt es echte Fehler?
# 3. Was muss manuell geprüft werden?
# 4. Was sind nur Optimierungshinweise?
# 5. Welche Bereiche wurden nicht geprüft?
#
# Detailtabellen dürfen aufklappbar sein.
# Die wichtigsten Fehler dürfen nicht nur in aufklappbaren Bereichen
# verborgen sein.


# ============================================================
# 16. AKTUELLER REFERENZSTAND
# ============================================================
#
# Beim geprüften Bericht für dogtruck.eu waren bereits sinnvoll
# umgesetzt:
#
# - HTTP 404/410 als wahrscheinlicher Linkfehler
# - HTTP 403 als „manuell prüfen“
# - Timeout als unbestimmtes Ergebnis
# - robots.txt als „nicht geprüft“
# - normale Weiterleitungen als eigene Gruppe
# - Ressourcenlimit als zusammengefasster Hinweis
# - Cache-Control, Kompression und CSP als Hinweise/Optimierungen
#
# Diese funktionierenden Regeln dürfen bei späteren Änderungen nicht
# wieder verschlechtert werden.


# ============================================================
# 17. ZIEL
# ============================================================
#
# Der Bericht soll zuerst die Frage beantworten:
#
#   „Was muss ich tatsächlich korrigieren?“
#
# Danach:
#
#   „Was muss ich manuell kontrollieren?“
#
# Danach:
#
#   „Was könnte ich verbessern?“
#
# Technische Informationen und vollständige Einzellisten folgen erst
# anschließend.
#
# ============================================================
# ENDE
# ============================================================

