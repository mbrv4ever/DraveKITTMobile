DraveKITT Mobile - KITT voor je telefoon (Kivy / Android)
=========================================================

Wat is het?
-----------
Een lichte KITT-app voor Android: een dashboard met rode scanner-balken en het
drakenlogo. Je typt of spreekt een vraag; KITT antwoordt en spreekt het hardop uit
met Androids eigen stem.

- Tekst-naar-spraak: via Androids ingebouwde stem (plyer).
- Spraak-naar-tekst: via Androids ingebouwde spraakherkenning (knop "Spreek").
  De eerste keer vraagt Android toestemming voor de microfoon.
- Het "brein" is bewust licht (tijd, datum, begroeting, KITT-antwoorden).

Verbinden met je pc (het "hoofdkwartier")
-----------------------------------------
Voor het ECHTE brein (groot model + online zoeken + weer) praat de app met een
servertje op je pc:
1. Start op je pc 'Start-KITT-server.bat' (in de map KITT-Server, naast DraveKITT).
   Die toont een adres, bv. http://192.168.1.50:8000.
2. Open DraveKITT op je telefoon -> knop 'Instellen' -> vul dat adres in -> Opslaan.
3. Telefoon en pc moeten op hetzelfde wifi zitten.
Werkt de pc/server even niet (bv. bij een update), dan zegt KITT netjes:
"Ik kan op dit moment geen verbinding maken met het hoofdkwartier" en geeft hij
zelf een licht antwoord. Later kunnen we 'van buitenshuis' toevoegen (via Tailscale).

Op de pc proberen
-----------------
  python main.py        (vereist: pip install kivy plyer)
Typen + antwoorden werkt; de stem hangt af van wat je pc heeft.

Naar Android bouwen
-------------------
Gebruik DraveAPK:
1. Start DraveAPK (run.bat).
2. "Bladeren..." -> kies deze map (DraveKITTMobile).
3. App-naam invullen (bv. DraveKITT); het icoon staat al klaar (logo.png).
4. "Bouw APK". Deze map heeft al een buildozer.spec (met plyer + microfoon-
   toestemming), dus die wordt gebruikt.
5. De .apk komt in de map "bin". Zet 'm op je telefoon en open hem.

Let op
------
- De eerste build duurt lang (Buildozer haalt de Android-gereedschappen op).
- Spraak werkt alleen op een echt toestel (met internet en microfoon-toestemming),
  niet in de pc-test.
