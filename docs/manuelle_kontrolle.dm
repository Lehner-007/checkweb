# ============================================================
# CHECKWEB – VERBESSERUNGEN AUS MANUELLER KONTROLLPRÜFUNG
# ============================================================
#
# ZWECK
# -----
# Diese Datei ergänzt die bestehenden checkweb-Vorgaben um Erkenntnisse
# aus der manuellen Kontrolle des erzeugten HTML-Prüfberichts und der
# Gegenprüfung mit Firefox.
#
# Diese Datei enthält nur Verbesserungsanforderungen.
# Bestehende funktionierende Prüfungen dürfen dadurch nicht verschlechtert
# oder entfernt werden.
#
# Datum: 27.09.2026
# ============================================================


# ============================================================
# 1. EXTERNE LINKS – KLARE BEWERTUNG
# ============================================================
#
# Externe Links müssen getrennt von Fehlern der eigenen Webseite
# ausgewertet werden.
#
# Kategorien:
#
# - INTERNER FEHLER
# - EXTERNER LINKFEHLER
# - MANUELL PRÜFEN
# - NICHT AUTOMATISCH BESTIMMBAR
# - WEITERLEITUNG
# - OK
#
# Ein Fehler einer externen Webseite darf nicht als technischer Fehler
# der geprüften Webseite dargestellt werden.
#
# Die Fundstelle des externen Links auf der eigenen Webseite muss
# trotzdem angegeben werden.


# ============================================================
# 2. HTTP 404 / 410
# ============================================================
#
# HTTP 404 und HTTP 410 werden als tatsächlicher Linkfehler gewertet,
# wenn die Antwort eindeutig vom Zielserver geliefert wurde.
#
# Bei externen Zielen lautet die Kategorie:
#
#   EXTERNER LINKFEHLER
#
# Beispiel aus der Kontrollprüfung:
#
#   Ziel:
#   https://apps.gnome.org/Geary/
#
#   Ergebnis:
#   HTTP 404
#
#   Manuelle Browserprüfung:
#   Die GNOME-Seite meldet, dass die Seite nicht gefunden wurde.
#
#   Bewertung:
#   Der checkweb-Befund ist bestätigt.
#
# Der Bericht soll in einem solchen Fall mindestens anzeigen:
#
# - HTTP-Code
# - Ziel-URL
# - intern / extern
# - Fundstelle
# - Datei bzw. Seite
# - Zeilennummer, sofern bestimmbar
# - Empfehlung: Link korrigieren oder entfernen


# ============================================================
# 3. HTTP 403 NICHT ALS DEFEKTEN LINK WERTEN
# ============================================================
#
# HTTP 403 bei automatisiertem Abruf darf nicht automatisch als
# defekter Link gewertet werden.
#
# Kategorie:
#
#   MANUELL PRÜFEN
#
# Empfohlener Berichtstext:
#
#   Automatisierter Abruf wurde mit HTTP 403 verweigert.
#   Dies bedeutet nicht automatisch, dass der Link defekt ist.
#   Ziel im normalen Browser manuell prüfen.
#
# Ein manuell erreichbares Ziel bleibt ein gültiger Link.
#
# Beispiel aus der Kontrollprüfung:
# Kodi war im Browser erreichbar, obwohl der automatisierte Abruf
# HTTP 403 lieferte.


# ============================================================
# 4. UNBESTIMMTE EXTERNE ZIELE
# ============================================================
#
# Kann checkweb ein externes Ziel nicht eindeutig bewerten, darf es
# nicht als Fehler gezählt werden.
#
# Kategorie:
#
#   NICHT AUTOMATISCH BESTIMMBAR
#
# Empfohlener Text:
#
#   Das Ziel konnte automatisiert nicht eindeutig geprüft werden.
#   Dies bedeutet nicht, dass der Link nicht erreichbar ist.
#   Manuelle Browserprüfung empfohlen.
#
# Bei der Kontrollprüfung wurden 10 als unbestimmt gemeldete externe
# Ziele manuell im Browser geprüft und waren erreichbar.
#
# Daraus folgt:
# Ein unbestimmtes automatisches Ergebnis darf niemals mit
# „nicht erreichbar“ gleichgesetzt werden.


# ============================================================
# 5. ZUSAMMENFASSUNG NACH FEHLERART TRENNEN
# ============================================================
#
# Die Zusammenfassung soll nicht nur einen allgemeinen Zähler
# „Fehler“ verwenden.
#
# Stattdessen getrennt darstellen:
#
# FEHLER DER EIGENEN WEBSEITE
# DEFEKTE EXTERNE LINKS
# MANUELL ZU PRÜFEN
# NICHT AUTOMATISCH BESTIMMBAR
# WARNUNGEN
# HINWEISE / OPTIMIERUNGEN
# WEITERLEITUNGEN
#
# Beispiel:
#
# Fehler der eigenen Webseite:       0
# Defekte externe Links:             1
# Manuell zu prüfen:                 1
# Nicht automatisch bestimmbar:    10
# Warnungen:                         0
# Hinweise / Optimierungen:         ...
# Weiterleitungen:                  ...
#
# Dadurch muss sofort erkennbar sein, ob die geprüfte Webseite selbst
# einen technischen Fehler enthält oder nur ein externer Link defekt ist.


# ============================================================
# 6. MANUELLE PRÜFUNG ALS EIGENE KATEGORIE
# ============================================================
#
# Ergebnisse, die eine Browserkontrolle benötigen, erhalten eine
# eigene Kategorie.
#
# Beispiele:
#
# - HTTP 403
# - Timeout
# - Rate-Limit
# - Serverantwort ohne eindeutige Aussage
# - Zugriff durch robots.txt eingeschränkt
# - sonstige automatisiert nicht eindeutig bestimmbare Antworten
#
# Diese Ergebnisse dürfen nicht gemeinsam mit bestätigten Fehlern
# gezählt werden.


# ============================================================
# 7. SEITENRESSOURCEN GETRENNT PRÜFEN
# ============================================================
#
# Eingebundene Ressourcen der eigenen Webseite müssen als eigene
# Ressourcentypen geprüft und dargestellt werden.
#
# Mindestens:
#
# - HTML
# - CSS
# - JavaScript
# - Bilder
# - Schriften
# - XHR / Fetch, sofern statisch oder technisch erfassbar
#
# Für jede Ressource, sofern verfügbar:
#
# - Ressourcentyp
# - URL / Pfad
# - HTTP-Status
# - einbindende Seite
# - intern / extern
#
# Fehlende eigene CSS-, JavaScript-, Bild- oder Schriftdateien sind
# höher zu gewichten als ein defekter externer Informationslink,
# weil sie die Funktion oder Darstellung der Webseite direkt
# beeinträchtigen können.


# ============================================================
# 8. RELATIVE RESSOURCENPFADE
# ============================================================
#
# Relative Ressourcenpfade müssen gegen die URL der jeweiligen
# Seite korrekt aufgelöst werden.
#
# Beispiele:
#
#   ../js/site.js
#   ./css/site.css
#   ../bilder/logo.png
#
# Erst nach korrekter URL-Auflösung darf die Ressource auf
# Erreichbarkeit geprüft werden.
#
# Ein relativer Pfad darf nicht allein wegen seiner Schreibweise als
# fehlerhaft bewertet werden.


# ============================================================
# 9. BROWSER-KONSOLE NICHT MIT WEBSEITENFEHLERN VERWECHSELN
# ============================================================
#
# Firefox-interne Meldungen oder Meldungen anderer Tabs dürfen nicht
# als Fehler der geprüften Webseite ausgewertet werden.
#
# Beispiele für nicht automatisch der Webseite zuzuordnende Meldungen:
#
# - Firefox RemoteSettings
# - Firefox Nimbus / Experimente
# - DevTools-Lokalisierung
# - Browser-interne Deprecated-Meldungen
# - Meldungen anderer geöffneter Webseiten
#
# Für eine Browserkontrolle ist ausschließlich der Kontext der
# tatsächlich geprüften Webseite maßgeblich.


# ============================================================
# 10. PRÜFUNG UNVOLLSTÄNDIG
# ============================================================
#
# „Prüfung unvollständig“ muss bedeuten:
#
# Mindestens ein Ziel oder Prüfbereich konnte nicht abschließend
# automatisch bewertet werden.
#
# Das bedeutet NICHT automatisch:
#
# - Webseite fehlerhaft
# - Link defekt
# - Ziel nicht erreichbar
#
# Im Bericht muss zusätzlich stehen, WARUM die Prüfung unvollständig
# ist und welche Ergebnisse noch manuell geprüft werden sollten.


# ============================================================
# 11. FUNDSTELLE BEI LINKFEHLERN
# ============================================================
#
# Bei jedem bestätigten Linkfehler soll checkweb möglichst genau
# angeben:
#
# - Quelldatei / Seite
# - Zeilennummer
# - Linktext, sofern bestimmbar
# - Ziel-URL
# - HTTP-Code
#
# Beispiel:
#
# EXTERNER LINKFEHLER
#
# Ziel:
# https://apps.gnome.org/Geary/
#
# HTTP:
# 404
#
# Gefunden in:
# software-zentrale.php
#
# Zeile:
# 775
#
# Empfehlung:
# Aktuellen Ziel-Link ermitteln und den alten Link ersetzen
# oder den Link entfernen.


# ============================================================
# 12. BESTEHENDE FUNKTIONIERENDE LOGIK BEIBEHALTEN
# ============================================================
#
# Folgende bereits funktionierende Regeln dürfen nicht wieder
# verschlechtert werden:
#
# - HTTP 404/410 als bestätigbarer Linkfehler
# - HTTP 403 nicht automatisch als defekter Link
# - Timeout als unbestimmtes Ergebnis
# - robots.txt als nicht automatisch geprüft
# - Weiterleitungen getrennt von Fehlern
# - Ressourcenlimit zusammengefasst darstellen
# - Hinweise/Optimierungen von Fehlern trennen
#
# Änderungen müssen mit bestehenden Testfällen regressionssicher
# geprüft werden.


# ============================================================
# 13. ZIEL DER VERBESSERUNG
# ============================================================
#
# Der Benutzer muss aus dem Bericht sofort erkennen können:
#
# 1. Hat meine eigene Webseite einen Fehler?
# 2. Ist nur ein externer Link defekt?
# 3. Welche Ergebnisse konnte checkweb nicht eindeutig bestimmen?
# 4. Welche Ziele muss ich manuell im Browser prüfen?
# 5. Welche Meldungen sind lediglich Hinweise oder Optimierungen?
#
# Ein automatisiert unbestimmtes Ergebnis darf niemals wie ein
# bestätigter Fehler dargestellt werden.
#
# ============================================================
# ENDE
# ============================================================
