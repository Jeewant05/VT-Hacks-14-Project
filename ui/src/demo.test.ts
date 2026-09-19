import { describe, expect, it } from 'vitest';
import { demoReducer, initialDemo, type DemoAction } from './demo';

const run = (...types: DemoAction['type'][]) => types.reduce((state, type) => demoReducer(state, { type }), initialDemo);

describe('guided demo completion gates', () => {
  it('does not skip identity and declaration steps', () => {
    expect(run('declared', 'accept', 'submit', 'completed')).toEqual(initialDemo);
  });
  it('stops at the mismatch until the user accepts a correction', () => {
    const state = run('start', 'verified', 'declared', 'submit', 'completed');
    expect(state.phase).toBe('conflict');
    expect(state.events.filter(event => event.id === 'conflict')).toHaveLength(1);
  });
  it('requires redeclaration and submission after acceptance', () => {
    expect(run('start', 'verified', 'declared', 'accept', 'completed').phase).toBe('correcting');
    expect(run('start', 'verified', 'declared', 'accept', 'redeclared', 'completed').phase).toBe('aligned');
    expect(run('start', 'verified', 'declared', 'accept', 'redeclared', 'submit', 'completed').phase).toBe('complete');
  });
  it('ignores duplicate actions and fully resets the simulation', () => {
    const state = run('start', 'verified', 'verified', 'declared', 'accept', 'accept');
    expect(new Set(state.events.map(event => event.id)).size).toBe(state.events.length);
    expect(demoReducer(state, { type: 'reset' })).toEqual(initialDemo);
  });
});
