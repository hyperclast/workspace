/**
 * Tests for paste code detection functionality.
 *
 * Tests the looksLikeCode and detectLanguage functions
 * to ensure code is properly detected and languages are identified.
 */

import { describe, test, expect } from "vitest";
import {
  looksLikeCode,
  detectLanguage,
  isInsideCodeBlock,
  transformPastedUrls,
} from "../../pasteCodeDetection.js";
import { EditorState } from "@codemirror/state";
import { codeFenceField } from "../../decorateFormatting.js";

describe("looksLikeCode", () => {
  describe("should detect code", () => {
    test("Python function definition", () => {
      const code = `def hello_world():
    print("Hello, World!")
    return True`;
      expect(looksLikeCode(code)).toBe(true);
    });

    test("JavaScript with const and arrow function", () => {
      const code = `const greet = (name) => {
  console.log(\`Hello, \${name}!\`);
  return true;
};`;
      expect(looksLikeCode(code)).toBe(true);
    });

    test("SQL query", () => {
      const code = `SELECT id, name, email
FROM users
WHERE active = 1
ORDER BY created_at DESC;`;
      expect(looksLikeCode(code)).toBe(true);
    });

    test("HTML markup", () => {
      const code = `<!DOCTYPE html>
<html>
<head>
  <title>Test</title>
</head>
<body>
  <div class="container">Hello</div>
</body>
</html>`;
      expect(looksLikeCode(code)).toBe(true);
    });

    test("JSON object", () => {
      const code = `{
  "name": "test",
  "version": "1.0.0",
  "dependencies": {
    "lodash": "^4.17.21"
  }
}`;
      expect(looksLikeCode(code)).toBe(true);
    });

    test("Ruby class definition", () => {
      const code = `class User
  attr_accessor :name, :email

  def initialize(name, email)
    @name = name
    @email = email
  end
end`;
      expect(looksLikeCode(code)).toBe(true);
    });

    test("Shell script with shebang", () => {
      const code = `#!/bin/bash
echo "Starting deployment..."
cd /var/www/app
git pull origin main
npm install`;
      expect(looksLikeCode(code)).toBe(true);
    });

    test("Go function", () => {
      const code = `package main

func main() {
    fmt.Println("Hello, World!")
}`;
      expect(looksLikeCode(code)).toBe(true);
    });

    test("Rust function", () => {
      const code = `fn main() {
    println!("Hello, World!");
    let x = 42;
}`;
      expect(looksLikeCode(code)).toBe(true);
    });

    test("Java class", () => {
      const code = `public class HelloWorld {
    public static void main(String[] args) {
        System.out.println("Hello, World!");
    }
}`;
      expect(looksLikeCode(code)).toBe(true);
    });

    test("Kotlin function", () => {
      const code = `fun main() {
    val message = "Hello, World!"
    println(message)
}`;
      expect(looksLikeCode(code)).toBe(true);
    });

    test("Lisp function", () => {
      const code = `(defun hello-world ()
  (format t "Hello, World!~%"))

(hello-world)`;
      expect(looksLikeCode(code)).toBe(true);
    });

    test("C/C++ with include", () => {
      const code = `#include <stdio.h>

int main() {
    printf("Hello, World!\\n");
    return 0;
}`;
      expect(looksLikeCode(code)).toBe(true);
    });

    test("CSS rules", () => {
      const code = `.container {
  display: flex;
  justify-content: center;
  padding: 1rem;
}`;
      expect(looksLikeCode(code)).toBe(true);
    });

    test("TypeScript interface", () => {
      const code = `interface User {
  id: number;
  name: string;
  email: string;
}`;
      expect(looksLikeCode(code)).toBe(true);
    });

    test("Code with method chaining", () => {
      const code = `const result = data
  .filter(x => x.active)
  .map(x => x.value)
  .reduce((a, b) => a + b, 0);`;
      expect(looksLikeCode(code)).toBe(true);
    });
  });

  describe("should NOT detect as code", () => {
    test("plain prose", () => {
      const text = `This is a simple paragraph of text. It contains
some sentences that are just normal writing. The words
here are all common English words that you would find
in any typical document or email.`;
      expect(looksLikeCode(text)).toBe(false);
    });

    test("short text", () => {
      const text = "Hello world";
      expect(looksLikeCode(text)).toBe(false);
    });

    test("email-like text", () => {
      const text = `Hi John,

I hope this email finds you well. I wanted to follow up
on our meeting from last week. The team has been making
good progress on the project, and we should be ready
to present the results by Friday.

Best regards,
Sarah`;
      expect(looksLikeCode(text)).toBe(false);
    });

    test("markdown-like bullet points", () => {
      const text = `Here are some things to remember:
- First, we need to check the requirements
- Then, we should review the design
- Finally, we can start the implementation
- This is just a simple list of tasks`;
      expect(looksLikeCode(text)).toBe(false);
    });

    test("empty string", () => {
      expect(looksLikeCode("")).toBe(false);
    });

    test("null/undefined", () => {
      expect(looksLikeCode(null)).toBe(false);
      expect(looksLikeCode(undefined)).toBe(false);
    });
  });

  describe("edge cases", () => {
    test("mixed code and prose - should follow dominant pattern", () => {
      // Mostly code with a comment
      const mostlyCode = `// This is a comment explaining the code
const x = 42;
const y = x * 2;
function calculate(a, b) {
  return a + b;
}`;
      expect(looksLikeCode(mostlyCode)).toBe(true);
    });

    test("very large paste - only analyzes first 50 lines", () => {
      // Generate 100 lines of code
      const lines = [];
      for (let i = 0; i < 100; i++) {
        lines.push(`const var${i} = ${i};`);
      }
      const code = lines.join("\n");
      expect(looksLikeCode(code)).toBe(true);
    });
  });
});

describe("detectLanguage", () => {
  test("detects Python", () => {
    expect(detectLanguage("def hello():\n    pass")).toBe("py");
    expect(detectLanguage("class MyClass:\n    pass")).toBe("py");
    expect(detectLanguage("import os\nprint(os.getcwd())")).toBe("py");
  });

  test("detects JavaScript", () => {
    expect(detectLanguage("const x = 42;")).toBe("js");
    expect(detectLanguage("function hello() {\n  return 1;\n}")).toBe("js");
    expect(detectLanguage("import React from 'react';")).toBe("js");
  });

  test("detects TypeScript", () => {
    expect(detectLanguage("interface User {\n  name: string;\n}")).toBe("ts");
    expect(detectLanguage("type Status = 'active' | 'inactive';")).toBe("ts");
    expect(detectLanguage("const x: number = 42;")).toBe("ts");
  });

  test("detects SQL", () => {
    expect(detectLanguage("SELECT * FROM users")).toBe("sql");
    expect(detectLanguage("INSERT INTO users (name) VALUES ('test')")).toBe("sql");
    expect(detectLanguage("UPDATE users SET active = 1")).toBe("sql");
  });

  test("detects HTML", () => {
    expect(detectLanguage("<!DOCTYPE html>\n<html>")).toBe("html");
    expect(detectLanguage("<html>\n<head>")).toBe("html");
  });

  test("detects XML", () => {
    expect(detectLanguage('<?xml version="1.0"?>')).toBe("xml");
  });

  test("detects JSON", () => {
    expect(detectLanguage('{"key": "value"}')).toBe("json");
    expect(detectLanguage('[\n  {"id": 1}\n]')).toBe("json");
  });

  test("detects Shell/Bash", () => {
    expect(detectLanguage("#!/bin/bash\necho hello")).toBe("sh");
    expect(detectLanguage("#!/usr/bin/env node")).toBe("js");
    expect(detectLanguage("#!/usr/bin/python")).toBe("py");
  });

  test("detects Go", () => {
    expect(detectLanguage("package main\n\nfunc main() {}")).toBe("go");
  });

  test("detects Rust", () => {
    expect(detectLanguage("fn main() -> Result<(), Error> {}")).toBe("rust");
  });

  test("detects Java", () => {
    expect(detectLanguage("public class Main {\n}")).toBe("java");
  });

  test("detects Kotlin", () => {
    expect(detectLanguage('fun main() {\n    println("Hello")\n}')).toBe("kotlin");
    expect(detectLanguage("data class User(val name: String)")).toBe("kotlin");
  });

  test("detects Lisp", () => {
    expect(detectLanguage('(defun hello () (print "hi"))')).toBe("lisp");
    expect(detectLanguage("(defmacro when (test &body body))")).toBe("lisp");
  });

  test("detects C/C++", () => {
    expect(detectLanguage("#include <stdio.h>\nint main() {}")).toBe("c");
    expect(detectLanguage('#include <iostream>\nstd::cout << "hi";')).toBe("cpp");
  });

  test("detects CSS", () => {
    expect(detectLanguage(".container {\n  display: flex;\n}")).toBe("css");
    expect(detectLanguage("#main {\n  color: red;\n}")).toBe("css");
  });

  test("detects PHP", () => {
    expect(detectLanguage("<?php\necho 'hello';")).toBe("php");
  });

  test("detects Ruby", () => {
    expect(detectLanguage("def hello\n  puts 'hi'\nend")).toBe("ruby");
    expect(detectLanguage("require 'rails'")).toBe("ruby");
  });

  test("returns empty string for unknown", () => {
    expect(detectLanguage("just some random text")).toBe("");
    expect(detectLanguage("")).toBe("");
  });
});

describe("isInsideCodeBlock", () => {
  function createState(content) {
    return EditorState.create({
      doc: content,
      extensions: [codeFenceField],
    });
  }

  test("returns false when not in code block", () => {
    const state = createState("Hello world\n\nSome text");
    expect(isInsideCodeBlock(state, 0)).toBe(false);
    expect(isInsideCodeBlock(state, 5)).toBe(false);
  });

  test("returns true when inside code block", () => {
    const content = "Hello\n```js\nconst x = 1;\n```\nEnd";
    const state = createState(content);
    // Position inside the code block (line 3)
    const line3Start = state.doc.line(3).from;
    expect(isInsideCodeBlock(state, line3Start)).toBe(true);
  });

  test("returns true for unclosed code block", () => {
    const content = "Hello\n```py\ndef hello():\n    pass";
    const state = createState(content);
    // Position inside the unclosed code block
    const line3Start = state.doc.line(3).from;
    expect(isInsideCodeBlock(state, line3Start)).toBe(true);
  });

  test("returns false after code block ends", () => {
    const content = "```\ncode\n```\nAfter";
    const state = createState(content);
    // Position on the "After" line
    const afterLine = state.doc.line(4).from;
    expect(isInsideCodeBlock(state, afterLine)).toBe(false);
  });
});

describe("transformPastedUrls", () => {
  describe("should transform bare URLs", () => {
    test("single URL", () => {
      expect(transformPastedUrls("https://example.com")).toBe(
        "[https://example.com](https://example.com) "
      );
    });

    test("URL with path", () => {
      expect(transformPastedUrls("https://example.com/path/to/page")).toBe(
        "[https://example.com/path/to/page](https://example.com/path/to/page) "
      );
    });

    test("URL with query string", () => {
      expect(transformPastedUrls("https://example.com/search?q=hello&lang=en")).toBe(
        "[https://example.com/search?q=hello&lang=en](https://example.com/search?q=hello&lang=en) "
      );
    });

    test("URL with fragment", () => {
      expect(transformPastedUrls("https://example.com/page#section")).toBe(
        "[https://example.com/page#section](https://example.com/page#section) "
      );
    });

    test("http URL", () => {
      expect(transformPastedUrls("http://example.com")).toBe(
        "[http://example.com](http://example.com) "
      );
    });

    test("URL embedded in text", () => {
      expect(transformPastedUrls("Check out https://example.com for more info")).toBe(
        "Check out [https://example.com](https://example.com) for more info"
      );
    });

    test("multiple URLs in text", () => {
      const input = "See https://one.com and https://two.com for details";
      const expected =
        "See [https://one.com](https://one.com) and [https://two.com](https://two.com) for details";
      expect(transformPastedUrls(input)).toBe(expected);
    });

    test("URL followed by period (sentence ending)", () => {
      expect(transformPastedUrls("Visit https://example.com.")).toBe(
        "Visit [https://example.com](https://example.com)."
      );
    });

    test("URL followed by comma", () => {
      expect(transformPastedUrls("See https://example.com, then continue")).toBe(
        "See [https://example.com](https://example.com), then continue"
      );
    });
  });

  describe("should NOT transform", () => {
    test("text without URLs", () => {
      expect(transformPastedUrls("Just some plain text")).toBeNull();
    });

    test("text with existing markdown links", () => {
      expect(transformPastedUrls("Check [this](https://example.com) out")).toBeNull();
    });

    test("text with angle-bracket links", () => {
      expect(transformPastedUrls("See <https://example.com> for details")).toBeNull();
    });

    test("text with markdown image syntax", () => {
      expect(transformPastedUrls("![alt](https://example.com/img.png)")).toBeNull();
    });

    test("empty string", () => {
      expect(transformPastedUrls("")).toBeNull();
    });

    test("null/undefined", () => {
      expect(transformPastedUrls(null)).toBeNull();
      expect(transformPastedUrls(undefined)).toBeNull();
    });

    test("URL inside backticks", () => {
      expect(transformPastedUrls("`https://example.com`")).toBeNull();
    });

    test("URL inside backticks with surrounding text", () => {
      expect(transformPastedUrls("Use `https://api.example.com/v1` as the base")).toBeNull();
    });
  });

  describe("mixed backtick and bare URLs", () => {
    test("transforms bare URL but skips backtick-wrapped URL", () => {
      expect(
        transformPastedUrls("See `https://api.example.com` and visit https://docs.example.com")
      ).toBe(
        "See `https://api.example.com` and visit [https://docs.example.com](https://docs.example.com) "
      );
    });
  });
});
