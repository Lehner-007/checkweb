# Bibliotheksübersicht

**Dokumentversion:** 1.0
**Dokumentiert für:** checkweb 1.4.8
**Bestandsaufnahme:** 22.10.2026 in einer Linux-Mint-22.3-Entwicklungs-VM. Die hier erfassten installierten Versionen beschreiben nur diese VM, nicht Josefs Zielrechner oder jedes erzeugte Paket. Sie sind keine aktuelle Sicherheitsbewertung.

Die Versionsnummer 1.0 gehört zu dieser Übersicht und ist unabhängig von der jeweils dokumentierten Programmversion checkweb. „Eingesetzt“ bedeutet, dass der Projektcode die Komponente tatsächlich importiert oder als externes Prüfwerkzeug aufruft. Eine Paketabhängigkeit kann verpflichtend oder optional sein; die Paketdeklaration ist in `packaging/build_deb.py` festgehalten. Python-Standardbibliothek und Systemwerkzeuge wie `util-linux` werden nicht als Python-Bibliotheken aufgeführt.

## Eingesetzte externe Komponenten

| Komponente | Zweck und Status | Upstream | Lizenz | Version / Prüfdatum | Einschränkungen |
| --- | --- | --- | --- | --- | --- |
| PyGObject / GTK 4 | GTK-Oberfläche; verpflichtende Laufzeitabhängigkeit | [PyGObject](https://gitlab.gnome.org/GNOME/pygobject), [GTK](https://www.gtk.org/) | LGPL-2.1-or-later (PyGObject); LGPL-2.1-or-later (GTK) | PyGObject 3.48.2 und GTK 4.14.5 in der VM, 22.10.2026 | GTK-Laufzeit und Introspektion sind installiert. Diese Versionsabfrage allein belegt keine vollständige GUI-Abnahme; dafür dienen die GTK-Abnahmeskripte. |
| beautifulsoup4 | HTML zerlegen und Dokumentstrukturen auswerten; verpflichtend | [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/bs4/doc/) | MIT | 4.12.3 in der VM, 22.10.2026 | Fehlertolerante Struktur- und Linkanalyse; ersetzt keinen vollständigen Konformitätsvalidator. |
| requests | HTTP(S)-Abrufe und Antwortverarbeitung; verpflichtend | [Requests](https://github.com/psf/requests) | Apache-2.0 | 2.31.0 in der VM, 22.10.2026 | Online-Prüfungen hängen zusätzlich von Netzwerk, Zielservern und den gesetzten Abrufgrenzen ab. |
| urllib3 | HTTP-Ausnahme `ReadTimeoutError`, als Requests-Abhängigkeit verwendet | [urllib3](https://github.com/urllib3/urllib3) | MIT | 2.0.7 in der VM, 22.10.2026 | Transitive Abhängigkeit; nicht separat in der DEB-Abhängigkeitsliste festgelegt. |
| html5lib | Zusätzliche HTML-Fehlerdiagnose; verpflichtend laut DEB-Metadaten | [html5lib](https://github.com/html5lib/html5lib-python) | MIT | 1.1 in der VM, 22.10.2026 | Erzeugt Diagnosen für die implementierten Prüfungen; ist keine vollständige Abdeckung sämtlicher Validator-Regeln. |
| tinycss2 | CSS-Tokenisierung, Syntaxdiagnosen und Ressourcenreferenzen; optional | [tinycss2](https://github.com/Kozea/tinycss2) | BSD-3-Clause | 1.2.1 in der VM, 22.10.2026 | Syntax-/Tokenanalyse, keine vollständige CSS-Regel- oder Stilprüfung. |
| lxml | Strukturierte XML-Prüfung; optional | [lxml](https://github.com/lxml/lxml) | BSD-3-Clause | 5.2.1 in der VM, 22.10.2026 | Optionale strukturierte Prüfung, keine Garantie für Gültigkeit gegen beliebige externe Schemas. |
| Pillow | Bildmetadaten- und Bildverarbeitung im Paketbau; optional für Laufzeitfunktionen | [Pillow](https://github.com/python-pillow/Pillow) | HPND | 10.2.0 in der VM, 22.10.2026 | Nicht für HTML-/CSS-Konformität. Paketbau importiert Pillow. |
| Node.js | Startet den JavaScript-Parser als begrenzten Unterprozess; optionales externes Werkzeug | [Node.js](https://nodejs.org/) | MIT | 18.19.1 in der VM, 22.10.2026 | Fehlt Node.js, können echte JavaScript-Parserprüfungen nicht laufen; die Anwendung kennzeichnet die betroffenen Prüfungen als nicht verfügbar. |
| Acorn | JavaScript-AST-Parser im Node-Unterprozess; optionales externes Werkzeug | [Acorn](https://github.com/acornjs/acorn) | MIT | 8.8.1 in der VM, 22.10.2026 | Benötigt Node.js und das Modul `acorn`. Kein Nachweis für die Version auf Josefs Zielrechner. |
| PHP CLI | PHP-Syntaxprüfung, wenn PHP-Dateien geprüft werden; optionales externes Werkzeug | [PHP](https://www.php.net/) | PHP-3.01 | 8.4.27 in der VM, 22.10.2026 | Wird nur für die entsprechende Syntaxprüfung aufgerufen; die VM-Version bestätigt nicht die Zielumgebung. |
| josef_basis (lokale Kopie) | Gemeinsam verwendete GUI-, Fenster-, Dialog-, Sprach-, Profil- und Hilfsmodule; Bestandteil des Projekts | Lokale Projektquelle: [`/home/josef/Labor/Python/josef_basis/integration`](/home/josef/Labor/Python/josef_basis/integration) | GPL-3.0-only | 0.1.0 laut mitgeliefertem Manifest; 22.10.2026 geprüft | Kopie liegt unter `modules/_vendor/josef_basis/`; Prüfsummen stehen in `modules/_vendor/JOSEF_BASIS.json`, Lizenztext daneben. Diese lokale Kopie wird zur Laufzeit verwendet; der Entwicklungsordner wird nicht benötigt. |

Die externen Komponenten sind nicht sämtlich verpflichtende Paketabhängigkeiten. Laut `packaging/build_deb.py` sind Python 3 ab 3.10, PyGObject/GTK 4, Beautiful Soup, Requests und html5lib als `Depends` angegeben. tinycss2, lxml, Pillow, PHP CLI, Node.js und Acorn stehen unter `Recommends`. urllib3 wird über Requests mitgebracht. Die konkrete Verfügbarkeit hängt vom Zielsystem und dessen Paketquellen ab.

## Abnahmekriterien

`python3 tests/run_complete_acceptance.py` prüft zunächst alle Laufzeitvoraussetzungen für die vollständige Abnahme, führt danach die unittest-Suite und alle GTK-Abnahmeskripte aus. Ein fehlendes Werkzeug, fehlende grafische Sitzung, fehlgeschlagener Test oder übersprungener Test ergibt einen Fehlerstatus; solche Läufe dürfen nicht als vollständige Abnahme gewertet werden. Paketmanager-Installation/Entfernung und eine visuelle Kontrolle am Zielrechner sind davon getrennte Abnahmeschritte und müssen separat protokolliert werden.

## Geprüfte Kandidaten, noch nicht integriert

Die Kandidaten wurden aus der vorliegenden Upstream-Recherche und dem Prüfbericht vom 22.10.2026 übernommen. Für diese Übersicht wurden keine Kandidaten installiert, keine konkreten Kandidatenversionen freigegeben und keine aktuelle Sicherheits- oder Mint-Kompatibilitätsprüfung durchgeführt.

| Kandidat | Vorgesehener Zweck | Upstream | Lizenz | Version / Prüfdatum | Integrationsstatus und Einschränkungen |
| --- | --- | --- | --- | --- | --- |
| Nu Html Checker | Zusätzliche HTML-Konformitätsdiagnosen | [Validator / Nu Html Checker](https://github.com/validator/validator) | MIT | Keine Version ausgewählt; Recherche-Stand 22.10.2026 | Nicht integriert. Zuerst zu prüfender Kandidat. Paketierung, Java-Anforderungen einer JAR-Variante, begrenzte lokale Eingabe und strukturierte Diagnosen sind vor Umsetzung zu prüfen. Keine automatische Reparatur. |
| Stylelint | Zusätzliche CSS-Regelprüfungen | [Stylelint](https://github.com/stylelint/stylelint) | MIT | Keine Version ausgewählt; Recherche-Stand 22.10.2026 | Nicht integriert. Nach Nu prüfen. Node-Kompatibilität und Paketierung offen. Nur mit programmkontrollierter Konfiguration betreiben; keine Projekt-Plugins oder ausführbaren Konfigurationen laden. |
| acorn-walk | Mögliche Vereinfachung der AST-Durchquerung | [acorn-walk](https://github.com/acornjs/acorn/tree/master/acorn-walk) | MIT | Keine Version ausgewählt; Recherche-Stand 22.10.2026 | Nicht integriert. Nur übernehmen, wenn ein konkreter Wartungsvorteil gegenüber der aktuellen Durchquerung nachgewiesen ist. Löst Scope-Erkennung nicht automatisch. |
| axe-core | Spätere automatisierte Barrierefreiheitsprüfung im Browser | [axe-core](https://github.com/dequelabs/axe-core) | MPL-2.0 | Keine Version ausgewählt; Recherche-Stand 22.10.2026 | Nicht integriert. Als eigene Browserfunktion behandeln; benötigt eine Browser-/Seitenausführungsumgebung und zählt nicht zur statischen Prüfung. |

## Lizenz- und Versionshinweise

Die Lizenzangaben beziehen sich auf die genannten Upstream-Projekte beziehungsweise die lokale Lizenzdatei der vendorten Bibliothek. Vor einer Veröffentlichung müssen die tatsächlich ausgelieferten Lizenztexte und etwaige gebündelte Abhängigkeiten mit dem erzeugten Paket abgeglichen werden. Die Versionsaufnahme vom 22.10.2026 ist eine Momentaufnahme der Entwicklungs-VM und kein Ersatz für die Bestandsaufnahme auf dem Zielsystem oder eine Prüfung auf bekannte Sicherheitslücken.
