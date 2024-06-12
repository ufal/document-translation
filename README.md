# Formatted document translation

Automatically translate documents with **formatted** text such as Word, Powerpoint, RTF, HTML but also XML or even PDF!

In this repository, we implement an end-to-end system for machine translation of documents. We build on top of [Okapi Framework](https://okapiframework.org/) and provide a simple simple script that extracts translatable, formatted text from documents and translates them, **preserving the formatting**. We preserve the in-line formatting by reinserting the markup into the translated document.

## Introduction

How is translating formatted text different from non-formatted text? Consider the following example:

- Original: `He is a <b>friend</b> of mine.`
- Input to the translator: `He is a friend of mine.`
- Translation: `Er ist mein Freund.`
- Reinserted markup: `Er ist mein <b>Freund</b>.`

Machine translation systems work best when the input is stripped of any formatting tags such as the bold tag `<b>`. This is because they have been mostly trained on data without these markup tags. When we get rid of the markup, the translation is more accurate but we introduce a new problem --- we need to reinsert the formatting tags back into the translation to preserve the original formatting.

We do this by running a word alignment model that gives us information about which word in the original sentence corresponds to which word in the translated sentence. We then reinsert the markup back into the translation using this information.