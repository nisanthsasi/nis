import { describe, it, expect } from 'vitest'
import { parseScreenplay, textToLines } from '../src/lib/screenplay'

const SCRIPT = `
VERI

Written by
Someone

FADE IN:

1 INT. MEERA'S KITCHEN - NIGHT 1

Rain hammers the tin roof. MEERA (34) stands at the sink, a PHONE
buzzing face-down on the counter behind her.

She does not turn.

RAVI (O.S.)
Are you going to answer that?

MEERA
(without turning)
No.

RAVI
It's the third time.

MEERA
Then it's the third time I'm not answering.

She finally picks up the phone. Looks at the screen. Puts it down.

CUT TO:

EXT. PADDY FIELD - DAWN

Mist. A single figure walks the bund toward camera.

(CONTINUED)

CONTINUED:

MEERA (CONT'D)
(to herself)
Enough.

THE END
`

describe('parseScreenplay', () => {
  const scenes = parseScreenplay(textToLines(SCRIPT))

  it('finds both scenes and ignores the title page', () => {
    expect(scenes).toHaveLength(2)
    expect(scenes[0].heading).toBe("INT. MEERA'S KITCHEN - NIGHT")
    expect(scenes[0].sceneNo).toBe('1')
    expect(scenes[1].heading).toBe('EXT. PADDY FIELD - DAWN')
    expect(scenes[1].sceneNo).toBe('2')
  })

  it('splits heading into int/ext, location and time', () => {
    expect(scenes[0].intExt).toBe('INT')
    expect(scenes[0].location).toBe("MEERA'S KITCHEN")
    expect(scenes[0].timeLabel).toBe('NIGHT')
    expect(scenes[1].intExt).toBe('EXT')
    expect(scenes[1].timeLabel).toBe('DAWN')
  })

  it('collects characters with extensions stripped', () => {
    expect(scenes[0].characters).toEqual(['RAVI', 'MEERA'])
    expect(scenes[1].characters).toEqual(['MEERA'])
  })

  it('separates action, dialogue and parentheticals', () => {
    const els = scenes[0].elements
    const types = els.map((e) => e.type)
    expect(types[0]).toBe('heading')
    expect(types[1]).toBe('action')
    expect(els[1].text).toMatch(/^Rain hammers the tin roof/)
    const dlg = els.filter((e) => e.type === 'dialogue')
    expect(dlg).toHaveLength(4)
    expect(dlg[0]).toMatchObject({ character: 'RAVI', text: 'Are you going to answer that?' })
    expect(els.find((e) => e.type === 'parenthetical')).toMatchObject({ character: 'MEERA', text: '(without turning)' })
    expect(els.filter((e) => e.type === 'transition').map((e) => e.text)).toEqual(['CUT TO:'])
  })

  it('skips CONTINUED markers and keeps CONT\'D dialogue', () => {
    const els = scenes[1].elements
    expect(els.some((e) => /CONTINUED/.test(e.text))).toBe(false)
    expect(els.filter((e) => e.type === 'dialogue')[0]).toMatchObject({ character: 'MEERA', text: 'Enough.' })
  })

  it('falls back to a single untitled scene when there are no headings', () => {
    const s = parseScreenplay(textToLines('Just some prose about a man and a boat.'))
    expect(s).toHaveLength(1)
    expect(s[0].heading).toBe('UNTITLED SCENE')
  })

  it('handles Fountain forced headings and cues', () => {
    const s = parseScreenplay(textToLines('.INT HOUSE - DAY\n\nA room.\n\n@McCLANE\nYippee.\n'))
    expect(s).toHaveLength(1)
    expect(s[0].intExt).toBe('INT')
    expect(s[0].characters).toEqual(['McCLANE'])
  })
})

describe('elementsToText round trip', () => {
  it('re-parses to the same elements', async () => {
    const { elementsToText } = await import('../src/lib/screenplay')
    const scenes = parseScreenplay(textToLines(SCRIPT))
    const again = parseScreenplay(textToLines(elementsToText(scenes[0].elements)))
    expect(again).toHaveLength(1)
    expect(again[0].elements.map((e) => [e.type, e.character ?? '', e.text])).toEqual(scenes[0].elements.map((e) => [e.type, e.character ?? '', e.text]))
  })
})
