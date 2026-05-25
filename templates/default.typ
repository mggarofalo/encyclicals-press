// Default edition template. SCOTUS slip-opinion register.
//
// Page: 6" x 9" trim, U.S. Reports margins (inner 0.75", outer 1.0",
// top 0.75", bottom 1.0"). Mirrored binding edge.
//
// The render module (src/encyclicals_press/render.py) prepends a header
// of metadata bindings (#let title = ...) and appends body content that
// uses the helper functions imported here.

#import "lib/typography.typ": (
  apply-body-styles,
  paragraph-num,
  section-heading,
  chapter-divider,
  salutation,
  dateline,
  signature,
  body-font,
  sans-font,
  muted,
)
#import "lib/titlepage.typ": title-page
#import "lib/colophon.typ": colophon

#let edition(
  title: "",
  subtitle: none,
  pope: "",
  promulgated: none,
  incipit: none,
  source-url: "",
  fetch-date: "",
  body,
) = {
  // Document-wide setup -------------------------------------------------
  set document(title: title, author: pope)
  set text(lang: "en")

  // Body page layout: 6x9 with mirrored margins.
  set page(
    width: 6in,
    height: 9in,
    margin: (inside: 0.75in, outside: 1in, top: 0.85in, bottom: 1in),
    header: context {
      let page-num = counter(page).get().first()
      if page-num <= 2 { return }
      let recto = calc.odd(page-num)
      let title-text = text(
        size: 8pt, font: sans-font, tracking: 0.18em, fill: muted,
      )[#upper(title)]
      let page-display = text(size: 8pt, font: sans-font, fill: muted)[#page-num]
      if recto {
        grid(columns: (1fr, auto), title-text, h(0.3em) + page-display)
      } else {
        grid(columns: (auto, 1fr), page-display + h(0.3em), align(right, title-text))
      }
    },
    footer: none,
  )

  // Title page (its own page setup overrides the body page).
  title-page(
    title: title,
    subtitle: subtitle,
    pope: pope,
    promulgated: promulgated,
    incipit: incipit,
  )

  // Body --------------------------------------------------------------
  pagebreak(to: "odd", weak: true)

  show: apply-body-styles
  // First few words of each major section in small caps. We rely on the
  // render module emitting #show-opening(...) marks at the right places.

  body

  // Colophon ----------------------------------------------------------
  pagebreak(to: "odd", weak: true)

  colophon(
    source-url: source-url,
    fetch-date: fetch-date,
  )
}

// Smallcap-opening for the first words of a section. Used by render.py
// at the start of each major section.
#let section-opening(words, rest) = {
  text(tracking: 0.04em)[#smallcaps(words)]
  rest
}
