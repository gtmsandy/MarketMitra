import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const css = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf8')

describe('index.css design tokens', () => {
  it('references only declared custom properties', () => {
    const declared = new Set([...css.matchAll(/(--[A-Za-z0-9_-]+)\s*:/g)].map((match) => match[1]))
    const referenced = new Set([...css.matchAll(/var\((--[A-Za-z0-9_-]+)\)/g)].map((match) => match[1]))
    expect([...referenced].filter((token) => !declared.has(token))).toEqual([])
  })
})
