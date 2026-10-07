import test from "node:test";
import assert from "node:assert/strict";
import {addSearchHistory, parseSearchHistory} from "../lib/search-history.ts";
test("history sanitizes corrupt storage and keeps only bounded distinct searches", () => {
 assert.deepEqual(parseSearchHistory('bad'),[]);
 assert.deepEqual(parseSearchHistory('{"query":"x"}'),[]);
 assert.deepEqual(parseSearchHistory('[null,3," 半导体 ","半导体","ABC","abc",""]'),["半导体","ABC"]);
 assert.equal(parseSearchHistory(JSON.stringify(Array.from({length:30},(_,i)=>String(i)))).length,20);
});
test("repeated search moves to front without keeping keystroke prefixes", () => {
 assert.deepEqual(addSearchHistory(["半导体","300893"]," 300893 "),["300893","半导体"]);
 assert.deepEqual(addSearchHistory(["半导体"]," "),["半导体"]);
});
