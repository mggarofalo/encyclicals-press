// SCOTUS-style title page. Centered, sober, no ornament.

#import "typography.typ": body-font, sans-font, muted

#let _roman-year(year) = {
  let v = year
  let pairs = (
    (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
    (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
    (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
  )
  let out = ""
  for pair in pairs {
    while v >= pair.at(0) {
      out += pair.at(1)
      v -= pair.at(0)
    }
  }
  out
}

#let title-page(
  title: "",
  subtitle: none,
  pope: "",
  promulgated: none,
  incipit: none,
) = {
  page(
    margin: (top: 1.6in, bottom: 1.4in, x: 1in),
    background: none,
    header: none,
    footer: none,
  )[
    #set align(center)
    #set par(justify: false, leading: 0.6em)

    // Rubric line at the top.
    #text(size: 10pt, tracking: 0.2em, fill: muted)[#smallcaps("Encyclical Letter")]

    #v(0.6in)

    // Title display.
    #text(size: 28pt, weight: "regular", tracking: 0.06em)[#smallcaps(lower(title))]

    #if subtitle != none [
      #v(0.4em)
      #text(size: 13pt, style: "italic", fill: muted)[#subtitle]
    ]

    #v(0.9in)

    // Pope's name in small caps.
    #text(size: 11pt, tracking: 0.2em, fill: muted)[#smallcaps("of his holiness")]

    #v(0.3em)

    #text(size: 16pt, tracking: 0.08em)[#smallcaps(lower(pope))]

    #v(1fr)

    // Latin incipit toward the foot, italic.
    #if incipit != none [
      #text(size: 12pt, style: "italic")[#incipit]
      #v(0.5em)
    ]

    // Promulgation date in Roman numerals.
    #if promulgated != none [
      #text(size: 10pt, tracking: 0.15em, fill: muted)[
        #smallcaps("A.D. " + _roman-year(promulgated.year()))
      ]
    ]
  ]
}
