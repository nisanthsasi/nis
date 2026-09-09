import type { DirectorProfile } from './types'

/**
 * Director "lens" profiles. These encode visual grammar, not biography, so the
 * shot-list engine, the reference search and the image prompts can be steered
 * by a director's habits. Prompts use styleVocabulary only, never the name.
 */
export const DIRECTORS: DirectorProfile[] = [
  {
    id: 'villeneuve', name: 'Denis Villeneuve', region: 'Canada / Hollywood', era: '2010s to now',
    summary: 'Monumental scale, slow push-ins, figures dwarfed by architecture, muted desaturated palettes, dread built through duration.',
    aspectRatio: '2.39:1', coverageStyle: 'long-take',
    shotSizes: ['EWS', 'WS', 'MS', 'CU'], angles: ['eye-level', 'low', 'overhead'],
    movements: ['push-in', 'static', 'crane', 'drone'], lensCharacter: 'spherical', lensRange: [21, 50],
    lightingKey: 'overcast', lightingQuality: 'soft',
    palette: ['#8c8578', '#3b3f45', '#c9a86a', '#1c1e22'], colorTags: ['desaturated', 'earth tones', 'amber', 'low contrast'],
    blocking: 'Characters small and still inside vast geometry; movement is the camera creeping, not the actor.',
    pacing: 'slow', averageShotSec: 7,
    styleVocabulary: ['monumental brutalist scale', 'soft diffused overcast light', 'muted desaturated tones', 'fog and haze depth', 'tiny human figure against immense structure', 'slow cinematic push-in', 'minimalist composition', 'silence and dread'],
    signatureMoves: ['Slow push-in on a still face', 'Overhead of a figure crossing empty ground', 'Silhouette in a doorway of light'],
    frameThrowerDirector: 'Denis Villeneuve',
  },
  {
    id: 'kubrick', name: 'Stanley Kubrick', region: 'USA / UK', era: '1950s to 1990s',
    summary: 'One-point perspective, symmetrical corridors, wide lenses close to faces, slow zooms, cold precise lighting.',
    aspectRatio: '1.85:1', coverageStyle: 'tableau',
    shotSizes: ['WS', 'MS', 'CU', 'EWS'], angles: ['eye-level', 'low'],
    movements: ['steadicam', 'zoom', 'static', 'tracking'], lensCharacter: 'wide', lensRange: [18, 35],
    lightingKey: 'practical', lightingQuality: 'hard',
    palette: ['#b71c1c', '#e0e0e0', '#1a237e', '#000000'], colorTags: ['high contrast', 'saturated', 'red accent', 'cool'],
    blocking: 'Actors placed on the center line; the room is the frame. The famous stare: chin down, eyes up, wide lens.',
    pacing: 'slow', averageShotSec: 8,
    styleVocabulary: ['perfect one-point perspective symmetry', 'wide-angle lens close to subject', 'long corridor vanishing point', 'cold clinical lighting', 'saturated primary color accents', 'unsettling stillness', 'geometric interior'],
    signatureMoves: ['Reverse steadicam tracking a walker', 'Slow zoom out from detail to tableau', 'The Kubrick stare'],
    frameThrowerDirector: 'Stanley Kubrick',
  },
  {
    id: 'fincher', name: 'David Fincher', region: 'USA', era: '1990s to now',
    summary: 'Locked-off precision, low-angle eye-lines, sickly green-yellow grade, motivated low light, no handheld ever.',
    aspectRatio: '2.39:1', coverageStyle: 'classical',
    shotSizes: ['MS', 'MCU', 'OTS', 'CU', 'WS'], angles: ['eye-level', 'low', 'shoulder-level'],
    movements: ['static', 'push-in', 'tracking', 'pan'], lensCharacter: 'spherical', lensRange: [27, 50],
    lightingKey: 'low-key', lightingQuality: 'motivated',
    palette: ['#c8b560', '#2e3b2e', '#0e0f0c', '#7a8b6d'], colorTags: ['desaturated', 'green', 'amber', 'low contrast'],
    blocking: 'Camera slightly below eye-line, moves only when the actor moves and stops when they stop. Coverage is complete and surgical.',
    pacing: 'measured', averageShotSec: 4,
    styleVocabulary: ['surgically precise static composition', 'dim motivated practical light', 'sickly green and amber grade', 'deep blacks', 'clean digital clarity', 'camera slightly below eye level', 'procedural cool mood'],
    signatureMoves: ['Camera pans exactly with a turned head', 'Slow push-in during confession', 'Wide of a lonely figure in an office at night'],
    frameThrowerDirector: 'David Fincher',
  },
  {
    id: 'wong-kar-wai', name: 'Wong Kar-wai', region: 'Hong Kong', era: '1990s to 2010s',
    summary: 'Frames within frames, step-printed slow motion, saturated neon and tungsten, bodies glimpsed past doorways and curtains.',
    aspectRatio: '1.85:1', coverageStyle: 'fragmented',
    shotSizes: ['MCU', 'CU', 'INSERT', 'MS'], angles: ['eye-level', 'hip-level', 'dutch'],
    movements: ['handheld', 'static', 'tracking', 'rack-focus'], lensCharacter: 'vintage', lensRange: [24, 85],
    lightingKey: 'neon', lightingQuality: 'soft',
    palette: ['#c62828', '#0f6e56', '#f2b134', '#1a1a2e'], colorTags: ['saturated', 'red accent', 'green', 'warm', 'neon'],
    blocking: 'Characters framed through obstructions: door edges, mirrors, curtains, smoke. Longing shown by proximity denied.',
    pacing: 'measured', averageShotSec: 5,
    styleVocabulary: ['foreground obstruction framing', 'saturated red and green neon', 'tungsten warmth', 'reflection in mirror or glass', 'rain-slick streets', 'step-printed motion blur', 'cramped romantic interior', 'longing and melancholy'],
    signatureMoves: ['Slow-motion walk past a noodle stall', 'Insert of hands, cigarette, cheongsam fabric', 'Two people in a corridor, never quite touching'],
    frameThrowerDirector: 'Wong Kar-wai',
  },
  {
    id: 'malick', name: 'Terrence Malick', region: 'USA', era: '1970s to now',
    summary: 'Magic-hour natural light only, wide lenses drifting steadicam, low angles toward sky, whispering voiceover, nature between people.',
    aspectRatio: '2.39:1', coverageStyle: 'observational',
    shotSizes: ['WS', 'MS', 'CU', 'INSERT'], angles: ['low', 'eye-level', 'worms-eye'],
    movements: ['steadicam', 'handheld', 'tracking', 'tilt'], lensCharacter: 'wide', lensRange: [14, 35],
    lightingKey: 'golden-hour', lightingQuality: 'back-lit',
    palette: ['#f6c177', '#9ac37e', '#7ba7bc', '#4a3b2a'], colorTags: ['golden', 'warm', 'natural', 'earth tones'],
    blocking: 'Actors improvise across fields and rooms; the camera drifts around them at hip height, often looking up.',
    pacing: 'slow', averageShotSec: 4,
    styleVocabulary: ['magic hour backlight', 'sun flare through leaves', 'wide-angle drifting camera', 'low angle toward sky', 'wheat field or tall grass', 'natural available light only', 'lyrical elegiac mood', 'hands touching nature'],
    signatureMoves: ['Camera circles a figure looking up', 'Hand trailing through grass', 'Curtain blowing in a sunlit room'],
    frameThrowerDirector: 'Terrence Malick',
  },
  {
    id: 'tarkovsky', name: 'Andrei Tarkovsky', region: 'USSR', era: '1960s to 1980s',
    summary: 'Sculpting in time: very long takes, slow creeping dolly, water, fire, wind, textures of decay, sepia and desaturated color.',
    aspectRatio: '4:3', coverageStyle: 'long-take',
    shotSizes: ['WS', 'MS', 'CU', 'EWS'], angles: ['eye-level', 'high'],
    movements: ['push-in', 'tracking', 'static', 'pan'], lensCharacter: 'spherical', lensRange: [28, 50],
    lightingKey: 'natural', lightingQuality: 'diffused',
    palette: ['#6e5a3e', '#9a9a8a', '#3c4a3a', '#d6c9a8'], colorTags: ['sepia', 'desaturated', 'earth tones', 'muted'],
    blocking: 'Characters move within one continuous shot; the camera creeps forward over minutes. Objects and elements carry meaning.',
    pacing: 'slow', averageShotSec: 25,
    styleVocabulary: ['very long take', 'slow creeping dolly', 'dripping water and damp textures', 'peeling walls and decay', 'sepia desaturated color', 'mist over a field', 'candle flame', 'metaphysical stillness'],
    signatureMoves: ['Minutes-long push-in through a room', 'Rain falling indoors', 'Figure walking away into fog'],
    frameThrowerDirector: 'Andrei Tarkovsky',
  },
  {
    id: 'ozu', name: 'Yasujirō Ozu', region: 'Japan', era: '1930s to 1960s',
    summary: 'Tatami-level static camera, 50mm only, characters speaking to camera in matched singles, pillow shots of empty rooms and laundry.',
    aspectRatio: '4:3', coverageStyle: 'tableau',
    shotSizes: ['MS', 'MCU', 'WS', 'INSERT'], angles: ['ground-level', 'eye-level'],
    movements: ['static'], lensCharacter: 'spherical', lensRange: [50, 50],
    lightingKey: 'high-key', lightingQuality: 'soft',
    palette: ['#e63b2e', '#f0e6d2', '#4b6b8a', '#8a7b5a'], colorTags: ['warm', 'muted', 'red accent', 'low contrast'],
    blocking: 'Seated figures at low camera height; eye-lines straight into lens; strict 360-degree space with graphic matches.',
    pacing: 'measured', averageShotSec: 6,
    styleVocabulary: ['low tatami-height static camera', 'frontal medium shot looking near camera', 'domestic Japanese interior', 'still-life pillow shot', 'soft even light', 'quiet restraint', 'balanced graphic composition'],
    signatureMoves: ['Pillow shot of an empty corridor', 'Matched frontal singles in conversation', 'Train passing in a wide'],
    frameThrowerDirector: 'Yasujirô Ozu',
  },
  {
    id: 'bong', name: 'Bong Joon-ho', region: 'South Korea', era: '2000s to now',
    summary: 'Vertical staging of class, precise lateral tracking, tonal whiplash, wides that let comedy and horror share the frame.',
    aspectRatio: '2.39:1', coverageStyle: 'classical',
    shotSizes: ['WS', 'MS', 'MCU', 'CU', 'TWO'], angles: ['eye-level', 'high', 'low'],
    movements: ['tracking', 'static', 'push-in', 'pan'], lensCharacter: 'spherical', lensRange: [27, 65],
    lightingKey: 'natural', lightingQuality: 'motivated',
    palette: ['#5c6b4a', '#c0b283', '#2b2b2b', '#8fa3b0'], colorTags: ['muted', 'green', 'earth tones', 'cool'],
    blocking: 'Stairs, levels and windows separate classes; characters cross lines in frame. Lateral moves reveal a second layer.',
    pacing: 'measured', averageShotSec: 4,
    styleVocabulary: ['vertical staircase staging', 'architectural window framing', 'precise lateral tracking', 'naturalistic motivated light', 'muted green and grey palette', 'dark comedy tension', 'rain-soaked urban night'],
    signatureMoves: ['Lateral track along a fence or wall', 'Wide with foreground and background action', 'Slow push-in ending on a stare'],
    frameThrowerDirector: 'Bong Joon-ho',
  },
  {
    id: 'anderson', name: 'Wes Anderson', region: 'USA', era: '1990s to now',
    summary: 'Flat planimetric symmetry, 90-degree whip pans, overhead inserts, pastel palettes, dollhouse cross-sections.',
    aspectRatio: '1.85:1', coverageStyle: 'tableau',
    shotSizes: ['WS', 'MS', 'INSERT', 'CU'], angles: ['eye-level', 'overhead'],
    movements: ['whip-pan', 'static', 'tracking', 'zoom'], lensCharacter: 'anamorphic', lensRange: [24, 40],
    lightingKey: 'high-key', lightingQuality: 'soft',
    palette: ['#f4c7c3', '#f2e394', '#8bb8d0', '#b5651d'], colorTags: ['pastel', 'saturated', 'warm', 'high contrast'],
    blocking: 'Actors face the camera dead-on, centered; groups arranged in flat rows; movement is lateral or a snap pan.',
    pacing: 'brisk', averageShotSec: 3,
    styleVocabulary: ['perfectly centered planimetric composition', 'pastel storybook palette', 'flat frontal staging', 'overhead flat-lay insert', 'symmetrical facade', 'meticulous vintage production design', 'deadpan whimsical mood'],
    signatureMoves: ['Overhead insert of objects arranged on a table', 'Whip pan between two speakers', 'Slow-motion group walk toward camera'],
    frameThrowerDirector: 'Wes Anderson',
  },
  {
    id: 'pta', name: 'Paul Thomas Anderson', region: 'USA', era: '1990s to now',
    summary: 'Long steadicam oners through crowded spaces, slow push-ins on faces, 70s zooms, warm anamorphic film texture.',
    aspectRatio: '2.39:1', coverageStyle: 'long-take',
    shotSizes: ['MS', 'CU', 'WS', 'TWO'], angles: ['eye-level', 'low'],
    movements: ['steadicam', 'push-in', 'zoom', 'tracking'], lensCharacter: 'anamorphic', lensRange: [35, 75],
    lightingKey: 'practical', lightingQuality: 'soft',
    palette: ['#c98a3e', '#5a3d2b', '#e8d6b3', '#2c2a28'], colorTags: ['warm', 'amber', 'earth tones', 'saturated'],
    blocking: 'Actors move through real spaces in one take; the camera follows then lands on a face and stays.',
    pacing: 'measured', averageShotSec: 9,
    styleVocabulary: ['warm 35mm anamorphic film grain', 'long steadicam oner', 'slow push-in on a face', '1970s period warmth', 'practical tungsten lamps', 'shallow anamorphic focus', 'intimate epic'],
    signatureMoves: ['Steadicam following a character through a party', 'Two-shot that slowly tightens over a whole conversation', 'Slow zoom on a listener'],
    frameThrowerDirector: 'Paul Thomas Anderson',
  },
  {
    id: 'nolan', name: 'Christopher Nolan', region: 'UK / USA', era: '2000s to now',
    summary: 'Large-format clarity, handheld urgency inside precise structure, cross-cut tension, cool steel palette, real scale.',
    aspectRatio: '2.39:1', coverageStyle: 'kinetic',
    shotSizes: ['CU', 'MS', 'EWS', 'MCU'], angles: ['eye-level', 'low', 'overhead'],
    movements: ['handheld', 'tracking', 'static', 'drone'], lensCharacter: 'spherical', lensRange: [40, 80],
    lightingKey: 'natural', lightingQuality: 'hard',
    palette: ['#7c8a99', '#1e2a38', '#d8dde2', '#a67c52'], colorTags: ['cool', 'desaturated', 'blue', 'high contrast'],
    blocking: 'Faces held tight while the world is vast; practical action photographed for real; intercut lines of tension.',
    pacing: 'brisk', averageShotSec: 3,
    styleVocabulary: ['large format IMAX clarity', 'cool steel-blue grade', 'handheld close-up urgency', 'vast real landscape', 'crisp hard daylight', 'practical scale', 'ticking-clock tension'],
    signatureMoves: ['Handheld CU intercut with epic wide', 'Overhead of vehicles in geometric landscape', 'Slow tilt up a huge structure'],
    frameThrowerDirector: 'Christopher Nolan',
  },
  {
    id: 'mani-ratnam', name: 'Mani Ratnam', region: 'Tamil cinema', era: '1980s to now',
    summary: 'Lyrical romance in chiaroscuro, rain and window light, backlit silhouettes, intimate two-shots, song staging in stylised space.',
    aspectRatio: '2.39:1', coverageStyle: 'classical',
    shotSizes: ['TWO', 'CU', 'MS', 'WS'], angles: ['eye-level', 'low'],
    movements: ['tracking', 'push-in', 'static', 'crane'], lensCharacter: 'spherical', lensRange: [35, 85],
    lightingKey: 'chiaroscuro', lightingQuality: 'back-lit',
    palette: ['#1b2a41', '#f0a202', '#5e6472', '#e6e6e6'], colorTags: ['high contrast', 'blue', 'amber', 'cool'],
    blocking: 'Lovers framed by doorways and window grilles; monsoon rain as texture; faces half in shadow.',
    pacing: 'measured', averageShotSec: 4,
    styleVocabulary: ['dramatic backlit silhouette', 'window light through grille pattern', 'monsoon rain glistening', 'half-lit face in shadow', 'blue night with warm lamp', 'lyrical romantic intimacy', 'South Indian urban interior'],
    signatureMoves: ['Backlit silhouette two-shot in a doorway', 'CU lit by a single shaft of light', 'Rain-streaked window between lovers'],
    frameThrowerDirector: 'Mani Ratnam',
  },
  {
    id: 'lijo', name: 'Lijo Jose Pellissery', region: 'Malayalam cinema', era: '2010s to now',
    summary: 'Chaotic long takes through crowds, wide lenses in tight village spaces, low angles, muddy earth tones, animal energy.',
    aspectRatio: '2.39:1', coverageStyle: 'kinetic',
    shotSizes: ['WS', 'MS', 'EWS', 'CU'], angles: ['low', 'eye-level', 'overhead'],
    movements: ['handheld', 'steadicam', 'tracking', 'drone'], lensCharacter: 'wide', lensRange: [16, 32],
    lightingKey: 'natural', lightingQuality: 'hard',
    palette: ['#5b4a2f', '#8a9a5b', '#2b2b2b', '#c9a227'], colorTags: ['earth tones', 'desaturated', 'green', 'muted'],
    blocking: 'Dozens of bodies moving through frame; the camera plunges into the crowd and comes out the other side.',
    pacing: 'frenetic', averageShotSec: 6,
    styleVocabulary: ['wide-angle immersion in a crowd', 'Kerala village mud and rain', 'low angle chaos', 'handheld long take', 'harsh tropical daylight', 'earthy muddy palette', 'feral kinetic energy', 'night lit by torches and headlights'],
    signatureMoves: ['Oner running through a crowd chasing something', 'Drone wide of tiny figures across paddy', 'Low-angle CU of a sweating face'],
    frameThrowerDirector: 'Lijo Jose Pellissery',
  },
  {
    id: 'dileesh', name: 'Dileesh Pothan', region: 'Malayalam cinema', era: '2010s to now',
    summary: 'Realist observation, natural light, unhurried two-shots, humour found in background action, unshowy handheld.',
    aspectRatio: '2.39:1', coverageStyle: 'observational',
    shotSizes: ['MS', 'TWO', 'WS', 'MCU'], angles: ['eye-level'],
    movements: ['handheld', 'static', 'pan'], lensCharacter: 'spherical', lensRange: [32, 50],
    lightingKey: 'natural', lightingQuality: 'soft',
    palette: ['#7a9b76', '#d9c8a9', '#4f4a41', '#a8b7c7'], colorTags: ['natural', 'green', 'muted', 'warm'],
    blocking: 'Life continues behind the scene; characters share the frame; cuts wait for behaviour, not lines.',
    pacing: 'measured', averageShotSec: 5,
    styleVocabulary: ['naturalistic Kerala small-town realism', 'soft daylight through a window', 'unforced handheld', 'background life in the frame', 'lived-in domestic clutter', 'gentle observational humour', 'green and ochre palette'],
    signatureMoves: ['Two-shot held while a third character passes', 'Slow pan following a glance', 'Wide of a verandah conversation'],
    frameThrowerDirector: 'Dileesh Pothan',
  },
  {
    id: 'kashyap', name: 'Anurag Kashyap', region: 'Hindi cinema', era: '2000s to now',
    summary: 'Gritty handheld, sodium-vapour night, long oners through alleys, dense frames, black humour in violence.',
    aspectRatio: '2.39:1', coverageStyle: 'kinetic',
    shotSizes: ['MS', 'CU', 'WS', 'OTS'], angles: ['eye-level', 'low', 'dutch'],
    movements: ['handheld', 'steadicam', 'tracking', 'whip-pan'], lensCharacter: 'spherical', lensRange: [24, 50],
    lightingKey: 'practical', lightingQuality: 'hard',
    palette: ['#e08a1e', '#2a1f14', '#6b7a3a', '#c33'], colorTags: ['amber', 'saturated', 'high contrast', 'warm'],
    blocking: 'Bodies crowd the lens in narrow lanes; violence staged in wides then punched in; camera is a participant.',
    pacing: 'frenetic', averageShotSec: 3,
    styleVocabulary: ['sodium-vapour orange night', 'North Indian alley grit', 'handheld immersion', 'dense cluttered frame', 'harsh practical bulbs', 'sweat and dust texture', 'raw kinetic violence'],
    signatureMoves: ['Steadicam oner through a lane during a chase', 'Dutch-angle CU under a bare bulb', 'Wide of a crowd erupting'],
    frameThrowerDirector: 'Anurag Kashyap',
  },
  {
    id: 'vetrimaaran', name: 'Vetrimaaran', region: 'Tamil cinema', era: '2000s to now',
    summary: 'Documentary-grade realism, brutal unflinching wides, dusty Madurai light, long takes of consequence, no glamour.',
    aspectRatio: '2.39:1', coverageStyle: 'observational',
    shotSizes: ['WS', 'MS', 'CU', 'FS'], angles: ['eye-level', 'high'],
    movements: ['handheld', 'static', 'tracking'], lensCharacter: 'spherical', lensRange: [28, 50],
    lightingKey: 'harsh-sun', lightingQuality: 'hard',
    palette: ['#b98b4e', '#4a3b2f', '#8c8c7a', '#1c1c1c'], colorTags: ['desaturated', 'earth tones', 'high contrast', 'sepia'],
    blocking: 'Violence and grief held in wide; the camera refuses to look away; faces weathered and unlit.',
    pacing: 'measured', averageShotSec: 6,
    styleVocabulary: ['dusty harsh Tamil Nadu sunlight', 'unflinching wide shot of violence aftermath', 'documentary handheld', 'weathered unglamorous faces', 'dry earth palette', 'social realism', 'sweat and dust'],
    signatureMoves: ['High wide of a body in a field', 'Long handheld take following a walk to a confrontation', 'CU of a face held past comfort'],
    frameThrowerDirector: 'Vetrimaaran',
  },
  {
    id: 'rgv', name: 'Ram Gopal Varma', region: 'Telugu / Hindi cinema', era: '1990s to 2000s',
    summary: 'Extreme low and high angles, wide lenses distorting faces, shadows of the underworld, camera placed where no one stands.',
    aspectRatio: '2.39:1', coverageStyle: 'fragmented',
    shotSizes: ['CU', 'ECU', 'WS', 'MS'], angles: ['low', 'dutch', 'overhead', 'worms-eye'],
    movements: ['static', 'handheld', 'push-in', 'crane'], lensCharacter: 'wide', lensRange: [14, 28],
    lightingKey: 'low-key', lightingQuality: 'hard',
    palette: ['#141414', '#c9b458', '#3d3d3d', '#7f1d1d'], colorTags: ['low contrast', 'desaturated', 'amber', 'monochrome'],
    blocking: 'Faces shoved into a wide lens from below; the room seen from the ceiling fan; power read through angle.',
    pacing: 'brisk', averageShotSec: 3,
    styleVocabulary: ['extreme low angle wide lens', 'face distorted close to lens', 'ceiling-fan overhead angle', 'Mumbai underworld shadow', 'hard single source light', 'menacing stillness', 'gritty gangster realism'],
    signatureMoves: ['Worms-eye of a don walking over camera', 'Overhead through a ceiling fan', 'ECU of eyes in near darkness'],
    frameThrowerDirector: 'Ram Gopal Varma',
  },
  {
    id: 'padmarajan', name: 'P. Padmarajan', region: 'Malayalam cinema', era: '1970s to 1990s',
    summary: 'Literary intimacy, monsoon light, quiet two-shots, sensual details, the Kerala landscape as emotional weather.',
    aspectRatio: '4:3', coverageStyle: 'classical',
    shotSizes: ['TWO', 'MS', 'CU', 'WS'], angles: ['eye-level'],
    movements: ['static', 'pan', 'push-in', 'tracking'], lensCharacter: 'vintage', lensRange: [35, 75],
    lightingKey: 'natural', lightingQuality: 'soft',
    palette: ['#4f7a5a', '#c9b79c', '#6a7b8c', '#3a2e2a'], colorTags: ['green', 'muted', 'warm', 'sepia'],
    blocking: 'Two people, a verandah, rain beyond; the cut comes on a glance; hands and objects carry desire.',
    pacing: 'slow', averageShotSec: 6,
    styleVocabulary: ['1980s Kerala monsoon melancholy', 'soft overcast daylight', 'lush wet green landscape', 'intimate verandah two-shot', 'vintage film softness', 'sensual detail of hands and cloth', 'literary quiet'],
    signatureMoves: ['Two-shot on a verandah with rain behind', 'CU of a face turning toward the window', 'Wide of a figure on a wet country road'],
    frameThrowerDirector: 'Padmarajan',
  },
  {
    id: 'bharathan', name: 'Bharathan', region: 'Malayalam cinema', era: '1970s to 1990s',
    summary: 'Painterly frames, earthy village textures, backlit dust and smoke, bodies and labour composed like canvases.',
    aspectRatio: '4:3', coverageStyle: 'tableau',
    shotSizes: ['WS', 'MS', 'CU', 'INSERT'], angles: ['eye-level', 'low'],
    movements: ['static', 'pan', 'tracking'], lensCharacter: 'vintage', lensRange: [35, 85],
    lightingKey: 'golden-hour', lightingQuality: 'back-lit',
    palette: ['#a35a2a', '#e0b464', '#4d5b3a', '#2a1f1b'], colorTags: ['warm', 'earth tones', 'golden', 'saturated'],
    blocking: 'Figures arranged against mud walls and river banks like a painting; labour as choreography.',
    pacing: 'measured', averageShotSec: 5,
    styleVocabulary: ['painterly composition', 'backlit dust and woodsmoke', 'earthy Kerala village textures', 'warm golden light on skin', 'river bank and mud wall', 'sensual folk realism', 'rich saturated earth palette'],
    signatureMoves: ['Backlit wide of workers in smoke', 'Insert of hands at a craft', 'Low angle of a figure against a warm sky'],
    frameThrowerDirector: 'Bharathan',
  },
  {
    id: 'gerwig', name: 'Greta Gerwig', region: 'USA', era: '2010s to now',
    summary: 'Warm ensemble energy, overlapping dialogue in wide two-shots, soft window light, saturated period color, brisk cutting.',
    aspectRatio: '1.85:1', coverageStyle: 'classical',
    shotSizes: ['TWO', 'MS', 'MCU', 'WS'], angles: ['eye-level'],
    movements: ['handheld', 'tracking', 'static', 'push-in'], lensCharacter: 'spherical', lensRange: [32, 50],
    lightingKey: 'natural', lightingQuality: 'soft',
    palette: ['#e9c46a', '#f4a261', '#2a9d8f', '#e76f51'], colorTags: ['warm', 'saturated', 'golden', 'pastel'],
    blocking: 'Sisters and friends pile into one frame; the camera keeps up with them; lines overlap.',
    pacing: 'brisk', averageShotSec: 3,
    styleVocabulary: ['warm ensemble two-shot', 'soft window daylight', 'saturated period costume color', 'lively overlapping energy', 'handheld warmth', 'domestic coming-of-age intimacy'],
    signatureMoves: ['Wide of a crowded family room', 'Tracking two friends walking and talking', 'MCU that catches a stifled laugh'],
    frameThrowerDirector: 'Greta Gerwig',
  },
]

export const CUSTOM_DIRECTOR: DirectorProfile = {
  id: 'custom', name: 'Custom grammar', region: 'You', era: 'Now',
  summary: 'Write your own visual grammar in the director panel; the engine reads shot sizes, lens, light and movement words from it.',
  aspectRatio: '2.39:1', coverageStyle: 'classical',
  shotSizes: ['WS', 'MS', 'OTS', 'CU'], angles: ['eye-level'],
  movements: ['static', 'push-in', 'handheld'], lensCharacter: 'spherical', lensRange: [24, 85],
  lightingKey: 'natural', lightingQuality: 'soft',
  palette: ['#888888', '#444444', '#cccccc', '#222222'], colorTags: ['natural'],
  blocking: 'Your call.', pacing: 'measured', averageShotSec: 4,
  styleVocabulary: ['cinematic film still'], signatureMoves: [],
}

export const ME_DIRECTOR: DirectorProfile = {
  ...CUSTOM_DIRECTOR,
  id: 'me', name: 'Me (my defaults)', region: 'You', era: 'Now',
  summary: 'Neutral classical coverage using your project defaults. Edit shots freely; nothing is imposed.',
}

export const ALL_DIRECTORS: DirectorProfile[] = [ME_DIRECTOR, CUSTOM_DIRECTOR, ...DIRECTORS]

export function getDirector(id: string): DirectorProfile {
  return ALL_DIRECTORS.find((d) => d.id === id) ?? ME_DIRECTOR
}

/**
 * Build a profile from free text for the "custom" director. Pulls recognisable
 * grammar words out of the text and falls back to CUSTOM_DIRECTOR otherwise.
 */
const customCache = new Map<string, DirectorProfile>()
export function directorFromText(text: string): DirectorProfile {
  const hit = customCache.get(text)
  if (hit) return hit
  const built = buildDirectorFromText(text)
  customCache.set(text, built)
  return built
}

function buildDirectorFromText(text: string): DirectorProfile {
  const t = text.toLowerCase()
  const p: DirectorProfile = { ...CUSTOM_DIRECTOR, styleVocabulary: [] }
  if (/long take|oner|single take/.test(t)) p.coverageStyle = 'long-take'
  else if (/handheld|kinetic|frenetic|chaos/.test(t)) p.coverageStyle = 'kinetic'
  else if (/tableau|symmetr|static|locked/.test(t)) p.coverageStyle = 'tableau'
  else if (/observ|realis|documentary/.test(t)) p.coverageStyle = 'observational'
  else if (/fragment|insert|detail|montage/.test(t)) p.coverageStyle = 'fragmented'
  if (/anamorphic/.test(t)) p.lensCharacter = 'anamorphic'
  else if (/vintage|old glass/.test(t)) p.lensCharacter = 'vintage'
  else if (/telephoto|long lens/.test(t)) p.lensCharacter = 'telephoto'
  else if (/wide lens|wide-angle|wide angle/.test(t)) p.lensCharacter = 'wide'
  if (/low[- ]key|dark|shadow/.test(t)) p.lightingKey = 'low-key'
  else if (/neon/.test(t)) p.lightingKey = 'neon'
  else if (/golden|magic hour/.test(t)) p.lightingKey = 'golden-hour'
  else if (/practical/.test(t)) p.lightingKey = 'practical'
  else if (/high[- ]key|bright/.test(t)) p.lightingKey = 'high-key'
  if (/handheld/.test(t)) p.movements = ['handheld', 'tracking', 'static']
  if (/steadicam|gimbal/.test(t)) p.movements = ['steadicam', 'tracking', 'push-in']
  if (/slow/.test(t)) p.pacing = 'slow'
  else if (/fast|quick|brisk/.test(t)) p.pacing = 'brisk'
  if (/2\.39|scope|widescreen/.test(t)) p.aspectRatio = '2.39:1'
  else if (/4:3|academy/.test(t)) p.aspectRatio = '4:3'
  else if (/16:9/.test(t)) p.aspectRatio = '16:9'
  const words = text.split(/[,.;\n]/).map((s) => s.trim()).filter((s) => s.length > 3 && s.length < 60)
  p.styleVocabulary = words.slice(0, 8).length ? words.slice(0, 8) : ['cinematic film still']
  p.summary = text.trim() || CUSTOM_DIRECTOR.summary
  return p
}
