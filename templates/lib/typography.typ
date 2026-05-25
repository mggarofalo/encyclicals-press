// Type-system primitives for encyclicals-press.
//
// Design language: U.S. Supreme Court slip opinion. Century-family body
// (TeX Gyre Schola), Inter only on folios. No drop caps, no ornament.

#let body-font = ("TeX Gyre Schola", "Century Schoolbook", "STIX Two Text", "Cambria")
#let sans-font = ("Inter", "Source Sans 3", "Segoe UI", "Arial")

#let body-size = 11pt
#let body-leading = 0.65em
#let footnote-size = 9pt
#let marginalia-size = 7pt
#let muted = rgb("#555")

// Apply the project-wide body typography. Use once at the top of the doc.
#let apply-body-styles(doc) = {
  set text(
    font: body-font,
    size: body-size,
    number-type: "old-style",
    weight: "regular",
  )
  set par(
    justify: true,
    leading: body-leading,
    first-line-indent: (amount: 1.2em, all: false),
    spacing: 0.75em,
  )
  // Footnotes: hung, smaller, with the marker tightly tucked.
  set footnote.entry(
    separator: line(length: 30%, stroke: 0.4pt + muted),
    gap: 0.4em,
    indent: 1em,
  )
  show footnote.entry: it => {
    set text(size: footnote-size)
    it
  }
  doc
}

// Width of the text block (page 6in − inside 0.75in − outside 1.0in).
// Used by paragraph-num to push the number past the right edge of the
// text block on recto pages.
#let _text-block-width = 4.25in
#let _margin-offset = 0.45in

// Marginal paragraph number. Old-style figures, Inter sans, muted.
// Pushed into the **outer** margin (right on recto, left on verso) by
// switching the dx offset based on page parity. Consumes no horizontal
// space — the wrapping ``box(width: 0pt)`` is a zero-width container so
// the placement floats relative to the current inline position.
#let paragraph-num(n) = context {
  let page-num = counter(page).get().first()
  let recto = calc.odd(page-num)
  let dx = if recto {
    _text-block-width + _margin-offset
  } else {
    -1 * _margin-offset
  }
  box(width: 0pt, place(left, dx: dx)[
    #text(size: marginalia-size, font: sans-font, fill: muted)[#n]
  ])
}

// Section heading. Centered small caps, no rules.
#let section-heading(title) = {
  v(1.2em, weak: true)
  align(center)[
    #text(size: body-size, tracking: 0.05em)[#smallcaps(lower(title))]
  ]
  v(0.4em, weak: true)
}

// Major Roman-numeral chapter divider (I., II., III., ...). Centered,
// small caps. The numeral itself sits on its own line for breathing room.
#let chapter-divider(numeral, title) = {
  v(2em, weak: true)
  align(center)[
    #text(size: body-size * 1.1, tracking: 0.1em)[#numeral] \
    #v(0.3em)
    #text(size: body-size, tracking: 0.05em)[#smallcaps(lower(title))]
  ]
  v(0.8em, weak: true)
}

// Salutation rubric block — italic small caps, centered, set off from body.
#let salutation(body) = {
  v(1.2em, weak: true)
  align(center)[
    #text(style: "italic", tracking: 0.04em)[#smallcaps(lower(body))]
  ]
  v(1em, weak: true)
}

// Closing dateline — italic, centered.
#let dateline(body) = {
  v(2em, weak: true)
  align(center)[
    #text(style: "italic")[#body]
  ]
  v(0.6em, weak: true)
}

// Papal signature — letterspaced caps, centered. Source text comes in
// already uppercase (``BENEDICTUS PP. XVI``); we letterspace it for display.
#let signature(body) = {
  align(center)[
    #text(tracking: 0.15em, weight: "regular")[#upper(body)]
  ]
  v(1.2em, weak: true)
}
