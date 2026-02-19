// Minimal placeholder bridge for transformers.js (used by tests as a stub)
// Reads JSON from stdin: { input: "..." }
// Writes JSON to stdout: { generated_text: "..." }

const fs = require('fs');

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', () => {
  try {
    const payload = JSON.parse(input || '{}');
    const text = payload.input || 'hi';
    // respond with a toy snippet
    const m = text.match(/(\d+)/);
    const n = m ? Number(m[1]) : 1;
    const phraseMatch = text.match(/say "?([^\"]+)"?/i);
    const phrase = phraseMatch ? phraseMatch[1] : text;
    const code = `for i in range(${n}):\n    say \"TRANSFORMERSJS-BRIDGE: ${phrase}\"\n`;
    console.log(JSON.stringify({ generated_text: code }));
  } catch (e) {
    console.log(JSON.stringify({ error: e.message }));
  }
});
