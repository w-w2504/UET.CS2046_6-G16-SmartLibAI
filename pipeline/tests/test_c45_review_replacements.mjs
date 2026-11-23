import test from 'node:test';
import assert from 'node:assert/strict';
import { reviewSourceMatches } from '../scripts/audit_c45_phase1.mjs';

test('review replacement must match source ID and URL; original URL is contextual', () => {
  const decision = { summary_url: 'https://old.example/book', source_replacements: {
    summary: {source_id: 'S_current', source_url: 'https://new.example/book'} } };
  assert.equal(reviewSourceMatches(decision, 'summary', {source_id:'S_current', source_url:'https://new.example/book'}), true);
  assert.equal(reviewSourceMatches(decision, 'summary', {source_id:'S_other', source_url:'https://new.example/book'}), false);
  assert.equal(reviewSourceMatches(decision, 'summary', {source_id:'S_current', source_url:'https://old.example/book'}), false);
  assert.equal(reviewSourceMatches({metadata_url:'https://old.example/book'}, 'metadata', {source_url:'https://old.example/book'}), true);
});
