# Third-party credits

## Coinc (MIT)

This project started from [Coinc](https://github.com/tomy0000000/Coinc) by
Tomy Hsieh, used under the MIT license. The conversion patterns and the circular
country-flag icons in `assets/flags/` and `assets/hints/` come from that project.

```
MIT License

Copyright (c) 2019 Tomy Hsieh

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Missing flags (FOK, KID, SHP, SLE, TVD, XCG, XPF, ZWG)

Downloaded from [flagcdn.com](https://flagcdn.com) (free, no key) and cropped to
the same circular format as the rest by `build/make.py`.

## English currency names

`vendor/currency_names.json` comes from
[@fawazahmed0/currency-api](https://github.com/fawazahmed0/currency-api) (MIT),
used only as a secondary search term.

## Fonts

Icon PNGs are generated at build time with system fonts (Avenir Next, Futura);
no font file is redistributed.
