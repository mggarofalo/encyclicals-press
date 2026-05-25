// Quiet colophon page — source acknowledgements, fonts, project mark.

#import "typography.typ": body-font, sans-font, muted

#let colophon(
  source-url: "",
  fetch-date: "",
  fonts: "TeX Gyre Schola and Inter",
) = {
  page(
    margin: (top: 2in, bottom: 1.5in, x: 1.2in),
    header: none,
    footer: none,
  )[
    #set align(center)
    #set par(justify: false, leading: 0.65em)
    #set text(size: 9.5pt, fill: muted)

    #text(size: 11pt, tracking: 0.15em)[#smallcaps("Colophon")]

    #v(1.5em)

    Typeset by #text(style: "italic")[encyclicals-press].

    #v(0.8em)

    Set in #fonts.

    #v(0.8em)

    #if source-url != "" [
      Source text fetched #fetch-date from
      #linebreak()
      #text(size: 8.5pt)[#source-url]
    ]

    #v(1fr)

    #text(size: 8.5pt)[
      Encyclical text © Libreria Editrice Vaticana.
      #linebreak()
      Typography and tooling MIT-licensed.
    ]
  ]
}
