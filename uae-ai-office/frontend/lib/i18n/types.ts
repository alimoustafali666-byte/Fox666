import type en from "./translations/en";

export type Locale = "en" | "ar";

export const LOCALES: Locale[] = ["en", "ar"];
export const DEFAULT_LOCALE: Locale = "en";

// `en.ts` is declared `as const` so Paths<T> below can walk its exact key
// structure, but that also makes every leaf a literal string type (e.g.
// "Business Intelligence", not `string`) -- which would force ar.ts (and
// any other locale) to contain the IDENTICAL English text to type-check.
// Widening every leaf to `string` keeps the shape check (a locale file
// must have exactly these nested keys) without constraining the values.
type DeepString<T> = T extends string ? string : { [K in keyof T]: DeepString<T[K]> };

export type Translations = DeepString<typeof en>;

// Every dot-path to a string leaf in the dictionary, e.g.
// "documents.errors.processFailed" -- gives t() full autocomplete and a
// compile error for a typo'd or removed key, without hand-maintaining a
// parallel list of key names.
type Join<K extends string, P extends string> = P extends "" ? K : `${K}.${P}`;

type Paths<T> = T extends string
  ? ""
  : {
      [K in keyof T & string]: Join<K, Paths<T[K]>>;
    }[keyof T & string];

export type TranslationKey = Paths<Translations>;

