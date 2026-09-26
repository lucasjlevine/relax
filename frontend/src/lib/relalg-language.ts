import {
  StreamLanguage,
  LanguageSupport,
  type StringStream,
} from "@codemirror/language";
import { tags as t } from "@lezer/highlight";

/** Keywords and operators (matched case-insensitively as whole words). */
const KEYWORD_RE =
  /^(pi|sigma|rho|tau|gamma|delta|union|intersect|except|minus|cross|division|join|natural|left|right|full|outer|semi|anti|inner|order|group|by|sort|distinct|and|or|xor|not|like|ilike|asc|desc|on|case|when|then|else|end|null|count|sum|avg|min|max)$/i;

const UNICODE_OP_RE = /^[πσρτγδ∪∩−×÷⋈⟕⟖⟗⋉⋊▷∧∨¬≠≤≥]/;

const HELPER_RE =
  /^(rownum|row_number|rand|length|strlen|upper|ucase|lower|lcase|concat|date|adddate|subdate|year|month|day|dayofmonth|hour|minute|second|now|abs|round|floor|ceil|ceiling|coalesce|add|sub|mul|div|mod|clock_timestamp|transaction_timestamp|statement_timestamp)$/i;

type RelAlgState = { inBlockComment: boolean };

const relalgParser = {
  name: "relalg",
  startState(): RelAlgState {
    return { inBlockComment: false };
  },
  token(stream: StringStream, state: RelAlgState): string | null {
    if (state.inBlockComment) {
      if (stream.match(/\*\//)) {
        state.inBlockComment = false;
        return "comment";
      }
      stream.next();
      stream.eatWhile(/[^*]/);
      return "comment";
    }

    if (stream.match(/^--/)) {
      stream.skipToEnd();
      return "comment";
    }
    if (stream.match(/^\/\*/)) {
      state.inBlockComment = true;
      return "comment";
    }

    if (stream.eatSpace()) return null;

    if (stream.match(/^'([^'\\]|\\.)*'/ ) || stream.match(/^"([^"\\]|\\.)*"/)) {
      return "string";
    }

    if (stream.match(/^-?\d+(\.\d+)?/)) return "number";

    if (stream.match(/^_->/) || stream.match(/^→/)) return "operator";

    if (stream.match(UNICODE_OP_RE)) return "keyword";

    if (stream.match(/^_\{/) || stream.match(/^[{}\[\](),.;*]/)) {
      return "bracket";
    }

    if (stream.match(/^(=|!=|<>|<=|>=|<|>|[%+\-/*])/)) return "operator";

    if (stream.match(/^[A-Za-z_][A-Za-z0-9_]*/)) {
      const word = stream.current();
      if (KEYWORD_RE.test(word)) return "keyword";
      if (HELPER_RE.test(word)) return "builtin";
      return "variableName";
    }

    if (stream.match(/^\./)) return "operator";

    stream.next();
    return null;
  },
  languageData: {
    commentTokens: { line: "--", block: { open: "/*", close: "*/" } },
    closeBrackets: { brackets: ["(", "[", "{", "'", '"'] },
  },
  tokenTable: {
    keyword: t.keyword,
    builtin: t.function(t.variableName),
    string: t.string,
    number: t.number,
    comment: t.comment,
    operator: t.operator,
    bracket: t.bracket,
    variableName: t.variableName,
  },
};

export const relalgLanguage = StreamLanguage.define(relalgParser);

export function relalg(): LanguageSupport {
  return new LanguageSupport(relalgLanguage);
}
