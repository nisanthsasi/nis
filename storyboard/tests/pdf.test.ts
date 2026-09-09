import { describe, it, expect } from 'vitest'
import { gridFor, pageCount } from '../src/export/pdf'

describe('pdf layout math', () => {
  it('chooses grids', () => {
    expect(gridFor(2)).toEqual({ cols: 2, rows: 1 })
    expect(gridFor(4)).toEqual({ cols: 2, rows: 2 })
    expect(gridFor(6)).toEqual({ cols: 3, rows: 2 })
  })
  it('never shares a page between scenes and keeps empty scenes', () => {
    expect(pageCount([4, 5, 0], 4)).toBe(1 + 2 + 1)
    expect(pageCount([13], 6)).toBe(3)
  })
})
