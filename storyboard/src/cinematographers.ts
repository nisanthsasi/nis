import type { CinematographerProfile } from './types'

/**
 * Cinematographer "lensing" profiles: format, focal-length ladder, light, colour,
 * camera temperament. Layered on top of a director's grammar by lens.ts.
 */
export const CINEMATOGRAPHERS: CinematographerProfile[] = [
  {
    id: 'deakins', name: 'Roger Deakins', region: 'UK / USA', era: '1980s to now',
    summary: 'One big soft source motivated by a window or a practical, clean uncluttered frames, silhouettes in fog and sodium light, almost never handheld.',
    format: '35mm spherical / Alexa large format', aspectRatio: '2.39:1', lensCharacter: 'spherical', lensLadder: { wide: 27, normal: 40, long: 75 },
    lightingKey: 'natural', lightingQuality: 'motivated', palette: ['#c2b8a3', '#2f3a44', '#e39b2d', '#0d0f12'], colorTags: ['desaturated', 'cool', 'amber', 'low contrast'],
    camera: 'fluid', depthOfField: 'mixed',
    styleVocabulary: ['single large soft source motivated by a window', 'clean minimal composition', 'silhouette against fog and sodium light', 'cool desaturated palette with one warm accent', 'precise restrained lighting', 'deep clean blacks'],
    signature: ['Silhouette in a doorway of orange light', 'Slow dolly with a locked horizon', 'Face lit by one window'],
    knownFor: ['Blade Runner 2049', '1917', 'Skyfall', 'No Country for Old Men', 'Sicario', 'The Shawshank Redemption'],
  },
  {
    id: 'lubezki', name: 'Emmanuel Lubezki', region: 'Mexico / USA', era: '1990s to now',
    summary: 'Natural light only, very wide lenses inches from faces, unbroken floating camera, magic hour and real sun flare, deep focus.',
    format: 'Alexa 65 / 35mm, natural light', aspectRatio: '2.39:1', lensCharacter: 'wide', lensLadder: { wide: 12, normal: 21, long: 35 },
    lightingKey: 'golden-hour', lightingQuality: 'back-lit', palette: ['#f2c27b', '#8aa37b', '#6f8fa8', '#3a2f26'], colorTags: ['golden', 'natural', 'warm', 'earth tones'],
    camera: 'handheld', depthOfField: 'deep',
    styleVocabulary: ['natural light only', 'magic hour backlight', 'ultra wide lens inches from the face', 'unbroken floating camera', 'real sun flare', 'deep focus with sky in frame'],
    signature: ['Oner circling a figure looking up', 'Wide lens on a face against sky', 'Camera drifting through a crowd in one take'],
    knownFor: ['Children of Men', 'The Tree of Life', 'Gravity', 'Birdman', 'The Revenant', 'Y Tu Mamá También'],
  },
  {
    id: 'doyle', name: 'Christopher Doyle', region: 'Hong Kong / Australia', era: '1980s to now',
    summary: 'Smeared step-printed motion, saturated neon and tungsten, handheld intimacy, reflections and obstructions, colour shifts from pushed stock.',
    format: '35mm, step-printed, pushed stock', aspectRatio: '1.85:1', lensCharacter: 'vintage', lensLadder: { wide: 24, normal: 35, long: 85 },
    lightingKey: 'neon', lightingQuality: 'soft', palette: ['#c62828', '#0f6e56', '#f2b134', '#1a1a2e'], colorTags: ['saturated', 'neon', 'red accent', 'green', 'warm'],
    camera: 'handheld', depthOfField: 'shallow',
    styleVocabulary: ['step-printed motion smear', 'saturated neon and tungsten', 'handheld intimacy', 'reflection in glass and mirror', 'foreground obstruction', 'pushed film grain and colour shift'],
    signature: ['Slow-motion walk with smeared background', 'Face seen through a rain-streaked window', 'Handheld chase through a wet market'],
    knownFor: ['Chungking Express', 'In the Mood for Love', 'Happy Together', 'Hero', 'Fallen Angels'],
  },
  {
    id: 'kaminski', name: 'Janusz Kamiński', region: 'Poland / USA', era: '1990s to now',
    summary: 'Hard backlight through smoke, blown-out windows, bleach-bypass desaturation, halation on highlights, shafts of light in haze.',
    format: '35mm, silver retention', aspectRatio: '1.85:1', lensCharacter: 'spherical', lensLadder: { wide: 21, normal: 35, long: 75 },
    lightingKey: 'high-key', lightingQuality: 'back-lit', palette: ['#dfe3e6', '#6b7580', '#b08d57', '#1b1d20'], colorTags: ['desaturated', 'high contrast', 'cool', 'bleach bypass'],
    camera: 'fluid', depthOfField: 'mixed',
    styleVocabulary: ['hard backlight through smoke', 'blown-out white windows', 'bleach-bypass desaturation', 'halation blooming on highlights', 'shafts of light in haze', 'push-in on an awed face'],
    signature: ['Figure silhouetted in a blown doorway', 'Dust and smoke lit from behind', 'Slow push-in on a face lit by what it sees'],
    knownFor: ["Schindler's List", 'Saving Private Ryan', 'Minority Report', 'Lincoln', 'War of the Worlds', 'The Fabelmans'],
  },
  {
    id: 'prieto', name: 'Rodrigo Prieto', region: 'Mexico / USA', era: '1990s to now',
    summary: 'Gritty handheld urgency, mixed stocks and cross-processed colour per storyline, bleach-bypass grit, saturated warmth.',
    format: 'mixed 35mm / Super 16 / digital', aspectRatio: '2.39:1', lensCharacter: 'spherical', lensLadder: { wide: 18, normal: 32, long: 65 },
    lightingKey: 'mixed', lightingQuality: 'hard', palette: ['#d98c3f', '#3b5a5e', '#1e1a17', '#c9c2a8'], colorTags: ['saturated', 'warm', 'high contrast', 'bleach bypass'],
    camera: 'handheld', depthOfField: 'mixed',
    styleVocabulary: ['gritty handheld urgency', 'cross-processed saturated colour', 'coarse film grain', 'sun-bleached city', 'mixed film stocks', 'raw available light'],
    signature: ['Handheld inside a moving car', 'Grainy wide of a hot city street', 'Storylines told in different stocks'],
    knownFor: ['Amores Perros', '21 Grams', 'Babel', 'Brokeback Mountain', 'The Irishman', 'Killers of the Flower Moon'],
  },
  {
    id: 'hoytema', name: 'Hoyte van Hoytema', region: 'Sweden / Netherlands', era: '2000s to now',
    summary: 'Large-format clarity, cool tungsten and daylight mix, vast negative space, handheld IMAX close-ups.',
    format: 'IMAX 65mm / 35mm', aspectRatio: '2.39:1', lensCharacter: 'spherical', lensLadder: { wide: 40, normal: 50, long: 80 },
    lightingKey: 'natural', lightingQuality: 'hard', palette: ['#7c8a99', '#1e2a38', '#d8dde2', '#a67c52'], colorTags: ['cool', 'desaturated', 'blue', 'high contrast'],
    camera: 'mixed', depthOfField: 'deep',
    styleVocabulary: ['large format IMAX clarity', 'cool daylight mixed with tungsten', 'vast negative space', 'handheld large-format close-up', 'crisp hard light', 'monumental landscape'],
    signature: ['IMAX close-up on a face in a cockpit', 'Tiny figure on an enormous plain', 'Practical spaceship interior with real light'],
    knownFor: ['Interstellar', 'Dunkirk', 'Oppenheimer', 'Her', 'Tinker Tailor Soldier Spy', 'Nope'],
  },
  {
    id: 'fraser', name: 'Greig Fraser', region: 'Australia', era: '2000s to now',
    summary: 'Grey diffused daylight, soft top-lit faces, muted sandy palette, grain-textured digital, shallow large-format focus.',
    format: 'Alexa LF / Alexa 65, film-emulation grain', aspectRatio: '2.39:1', lensCharacter: 'spherical', lensLadder: { wide: 32, normal: 50, long: 100 },
    lightingKey: 'overcast', lightingQuality: 'top-lit', palette: ['#b7a98d', '#4d4a45', '#2a2622', '#c98a4b'], colorTags: ['desaturated', 'earth tones', 'low contrast', 'muted'],
    camera: 'fluid', depthOfField: 'shallow',
    styleVocabulary: ['grey diffused daylight', 'soft top light on faces', 'muted sandy palette', 'grain-textured digital image', 'shallow large-format focus', 'dust in the air'],
    signature: ['Face half in soft shadow', 'Overcast desert wide', 'Slow push through haze'],
    knownFor: ['Dune', 'Zero Dark Thirty', 'Rogue One', 'The Batman', 'Lion', 'Killing Them Softly'],
  },
  {
    id: 'bradford-young', name: 'Bradford Young', region: 'USA', era: '2010s to now',
    summary: 'Underexposed rich shadows, soft top light on dark skin, warm smoky ambience, almost no fill.',
    format: 'Alexa / 35mm, underexposed', aspectRatio: '2.39:1', lensCharacter: 'vintage', lensLadder: { wide: 29, normal: 40, long: 65 },
    lightingKey: 'low-key', lightingQuality: 'top-lit', palette: ['#3a2a22', '#a66a3a', '#1a1614', '#8f8a7e'], colorTags: ['warm', 'low contrast', 'amber', 'muted'],
    camera: 'fluid', depthOfField: 'shallow',
    styleVocabulary: ['underexposed rich shadows', 'soft top light on dark skin', 'warm smoky ambience', 'minimal fill light', 'vintage glass softness', 'quiet intimate darkness'],
    signature: ['Face emerging from near-black', 'Window light falling across a room', 'Warm practical in a dark interior'],
    knownFor: ['Arrival', 'Selma', 'A Most Violent Year', 'Solo', 'When They See Us', 'Pariah'],
  },
  {
    id: 'cronenweth', name: 'Jeff Cronenweth', region: 'USA', era: '1990s to now',
    summary: 'Dim digital cleanliness, green-yellow grade, practical-motivated low light, locked-off precision.',
    format: 'RED digital', aspectRatio: '2.39:1', lensCharacter: 'spherical', lensLadder: { wide: 27, normal: 35, long: 50 },
    lightingKey: 'low-key', lightingQuality: 'motivated', palette: ['#c8b560', '#2e3b2e', '#0e0f0c', '#7a8b6d'], colorTags: ['desaturated', 'green', 'amber', 'low contrast'],
    camera: 'locked', depthOfField: 'mixed',
    styleVocabulary: ['dim clean digital image', 'sickly green-yellow grade', 'practical-motivated low light', 'deep noiseless blacks', 'camera below eye level', 'clinical stillness'],
    signature: ['Office at night lit by monitors', 'Face under a single tungsten practical', 'Static wide of a lonely room'],
    knownFor: ['Fight Club', 'The Social Network', 'The Girl with the Dragon Tattoo', 'Gone Girl'],
  },
  {
    id: 'elswit', name: 'Robert Elswit', region: 'USA', era: '1980s to now',
    summary: 'Warm anamorphic film, 1970s halation, long steadicam moves, practical tungsten lamps.',
    format: '35mm anamorphic', aspectRatio: '2.39:1', lensCharacter: 'anamorphic', lensLadder: { wide: 35, normal: 50, long: 75 },
    lightingKey: 'practical', lightingQuality: 'soft', palette: ['#c98a3e', '#5a3d2b', '#e8d6b3', '#2c2a28'], colorTags: ['warm', 'amber', 'earth tones', 'saturated'],
    camera: 'fluid', depthOfField: 'shallow',
    styleVocabulary: ['warm 35mm anamorphic grain', '1970s halation', 'long steadicam move', 'practical tungsten lamps', 'oval bokeh', 'period warmth'],
    signature: ['Steadicam through a party', 'Two-shot slowly tightening', 'Horizontal flare across a night exterior'],
    knownFor: ['Boogie Nights', 'Magnolia', 'There Will Be Blood', 'Nightcrawler', 'Michael Clayton'],
  },
  {
    id: 'yeoman', name: 'Robert Yeoman', region: 'USA', era: '1990s to now',
    summary: 'Flat frontal even light, pastel saturated production colour, planimetric symmetry, anamorphic or 16mm by film.',
    format: '35mm anamorphic / 16mm', aspectRatio: '1.85:1', lensCharacter: 'anamorphic', lensLadder: { wide: 27, normal: 40, long: 50 },
    lightingKey: 'high-key', lightingQuality: 'soft', palette: ['#f4c7c3', '#f2e394', '#8bb8d0', '#b5651d'], colorTags: ['pastel', 'saturated', 'warm', 'high contrast'],
    camera: 'locked', depthOfField: 'deep',
    styleVocabulary: ['flat frontal even light', 'pastel saturated production design', 'planimetric symmetry', 'storybook clarity', 'centered composition', 'snap pan'],
    signature: ['Overhead flat-lay insert', 'Centered frontal portrait', 'Lateral dolly past a cross-section set'],
    knownFor: ['The Grand Budapest Hotel', 'The Royal Tenenbaums', 'Moonrise Kingdom', 'Rushmore', 'Bridesmaids'],
  },
  {
    id: 'hong-kyung-pyo', name: 'Hong Kyung-pyo', region: 'South Korea', era: '2000s to now',
    summary: 'Naturalistic Korean interiors, muted green-grey palette, lateral tracking, motivated daylight and rain.',
    format: 'Alexa 65 / 35mm', aspectRatio: '2.39:1', lensCharacter: 'spherical', lensLadder: { wide: 27, normal: 40, long: 65 },
    lightingKey: 'natural', lightingQuality: 'motivated', palette: ['#5c6b4a', '#c0b283', '#2b2b2b', '#8fa3b0'], colorTags: ['muted', 'green', 'earth tones', 'cool'],
    camera: 'fluid', depthOfField: 'mixed',
    styleVocabulary: ['naturalistic interior daylight', 'muted green-grey palette', 'precise lateral tracking', 'rain-soaked night', 'architectural window framing', 'clean large-format depth'],
    signature: ['Track along a garden wall', 'Basement window at street level', 'Rain in sodium light'],
    knownFor: ['Parasite', 'Burning', 'Snowpiercer', 'Mother', 'Decision to Leave'],
  },
  {
    id: 'chung-hoon', name: 'Chung Chung-hoon', region: 'South Korea', era: '2000s to now',
    summary: 'Baroque ornate framing, saturated jewel tones, hard graphic shadows, elaborate dolly and crane choreography.',
    format: '35mm / digital', aspectRatio: '2.39:1', lensCharacter: 'spherical', lensLadder: { wide: 24, normal: 35, long: 85 },
    lightingKey: 'low-key', lightingQuality: 'hard', palette: ['#8b1e2d', '#1f4d3a', '#e6c26b', '#141416'], colorTags: ['saturated', 'red accent', 'green', 'high contrast'],
    camera: 'fluid', depthOfField: 'shallow',
    styleVocabulary: ['baroque ornate framing', 'saturated jewel tones', 'hard graphic shadows', 'elaborate camera choreography', 'symmetry broken by violence', 'polished period texture'],
    signature: ['Lateral corridor fight in one shot', 'Overhead of a body on patterned floor', 'Slow crane down through a window'],
    knownFor: ['Oldboy', 'The Handmaiden', 'Stoker', 'Last Night in Soho', 'It'],
  },
  {
    id: 'dion-beebe', name: 'Dion Beebe', region: 'Australia / USA', era: '1990s to now',
    summary: 'Grainy digital night, long lenses turning city lights into bokeh, available urban light, cool blue palette.',
    format: 'early digital (Viper) / Alexa, night exteriors', aspectRatio: '2.39:1', lensCharacter: 'telephoto', lensLadder: { wide: 21, normal: 35, long: 100 },
    lightingKey: 'practical', lightingQuality: 'soft', palette: ['#1e2f4a', '#f0a45a', '#6f7f8f', '#0a0c10'], colorTags: ['cool', 'blue', 'neon', 'desaturated'],
    camera: 'mixed', depthOfField: 'shallow',
    styleVocabulary: ['grainy digital night', 'long lens city bokeh', 'available urban light', 'cool blue palette', 'sky glow over a city', 'handheld in a moving car'],
    signature: ['Taxi interior lit by the city', 'Long-lens profile against skyline', 'Coyote crossing an empty avenue'],
    knownFor: ['Collateral', 'Miami Vice', 'Chicago', 'Memoirs of a Geisha', 'Edge of Tomorrow'],
  },
  {
    id: 'santosh-sivan', name: 'Santosh Sivan', region: 'India', era: '1980s to now',
    summary: 'Dramatic backlight and smoke, monsoon glisten, blue night with a warm lamp, a single shaft of light through a grille, romantic diffusion.',
    format: '35mm', aspectRatio: '2.39:1', lensCharacter: 'spherical', lensLadder: { wide: 24, normal: 50, long: 135 },
    lightingKey: 'chiaroscuro', lightingQuality: 'back-lit', palette: ['#1b2a41', '#f0a202', '#5e6472', '#e6e6e6'], colorTags: ['high contrast', 'blue', 'amber', 'cool'],
    camera: 'fluid', depthOfField: 'shallow',
    styleVocabulary: ['dramatic backlight through smoke', 'monsoon rain glistening', 'blue night with one warm lamp', 'shaft of light through a grille', 'romantic soft diffusion', 'long lens compression on faces'],
    signature: ['Silhouette two-shot in a doorway', 'Face lit by a single shaft', 'Rain against a bright window'],
    knownFor: ['Roja', 'Thalapathi', 'Iruvar', 'Dil Se..', 'Asoka', 'The Terrorist'],
  },
  {
    id: 'pc-sreeram', name: 'P.C. Sreeram', region: 'India', era: '1980s to now',
    summary: 'Pools of tungsten light in darkness, smoky low-key interiors, bounced soft window light, 1980s Madras texture.',
    format: '35mm', aspectRatio: '1.85:1', lensCharacter: 'spherical', lensLadder: { wide: 28, normal: 50, long: 85 },
    lightingKey: 'low-key', lightingQuality: 'soft', palette: ['#6b4a2b', '#d9b26f', '#1b1a17', '#8a7b6a'], colorTags: ['sepia', 'amber', 'low contrast', 'warm'],
    camera: 'fluid', depthOfField: 'mixed',
    styleVocabulary: ['pools of tungsten light in darkness', 'smoky low-key interior', 'bounced soft window light', 'sepia warmth', 'unlit background falling to black', 'realist 1980s texture'],
    signature: ['Face lit from a single lamp in a dark room', 'Backlit smoke in a godown', 'Window light on a kitchen wall'],
    knownFor: ['Nayakan', 'Mouna Ragam', 'Agni Natchathiram', 'Thevar Magan', 'Alaipayuthey', 'Kuruthipunal'],
  },
  {
    id: 'ravi-varman', name: 'Ravi Varman', region: 'India', era: '2000s to now',
    summary: 'Lush saturated colour, golden backlight, grand-scale period richness, flowing anamorphic camera.',
    format: 'Alexa anamorphic', aspectRatio: '2.39:1', lensCharacter: 'anamorphic', lensLadder: { wide: 32, normal: 50, long: 100 },
    lightingKey: 'golden-hour', lightingQuality: 'back-lit', palette: ['#d9a441', '#7a2e2e', '#2c4a5e', '#f1e3c4'], colorTags: ['golden', 'saturated', 'warm', 'high contrast'],
    camera: 'fluid', depthOfField: 'shallow',
    styleVocabulary: ['lush saturated colour', 'golden backlight', 'grand period richness', 'flowing anamorphic camera', 'oval bokeh on jewellery and rain', 'painterly warmth'],
    signature: ['Crane over a festival crowd', 'Backlit rain on a lover\'s face', 'Anamorphic flare across a palace hall'],
    knownFor: ['Ponniyin Selvan', 'Kaatru Veliyidai', 'Barfi!', 'Jagga Jasoos', 'Goliyon Ki Raasleela Ram-Leela'],
  },
  {
    id: 'rajeev-ravi', name: 'Rajeev Ravi', region: 'India', era: '2000s to now',
    summary: 'Raw handheld realism, harsh available light, Mumbai and Kerala street grit, unlit nights held together by practicals.',
    format: '35mm / digital, available light', aspectRatio: '2.39:1', lensCharacter: 'spherical', lensLadder: { wide: 24, normal: 35, long: 50 },
    lightingKey: 'natural', lightingQuality: 'hard', palette: ['#8a6d3b', '#3c3a36', '#b5b0a3', '#171614'], colorTags: ['desaturated', 'earth tones', 'muted', 'high contrast'],
    camera: 'handheld', depthOfField: 'deep',
    styleVocabulary: ['raw handheld realism', 'harsh available light', 'street grit and dust', 'unlit night with bare bulbs', 'documentary immediacy', 'sweat-sheen skin'],
    signature: ['Handheld follow through a lane', 'Wide of a crowd under a bare bulb', 'Unlit face by a doorway'],
    knownFor: ['Gangs of Wasseypur', 'Dev.D', 'Kammatipaadam', 'Thuramukham', 'Thondimuthalum Driksakshiyum'],
  },
  {
    id: 'girish-gangadharan', name: 'Girish Gangadharan', region: 'India', era: '2010s to now',
    summary: 'Wide-angle immersion in crowds, torchlight and headlights at night, mud, rain and sweat, chaotic long takes.',
    format: 'digital, wide primes', aspectRatio: '2.39:1', lensCharacter: 'wide', lensLadder: { wide: 14, normal: 24, long: 35 },
    lightingKey: 'natural', lightingQuality: 'hard', palette: ['#5b4a2f', '#8a9a5b', '#2b2b2b', '#c9a227'], colorTags: ['earth tones', 'desaturated', 'green', 'muted'],
    camera: 'handheld', depthOfField: 'deep',
    styleVocabulary: ['wide-angle immersion in a crowd', 'torchlight and headlights at night', 'mud rain and sweat texture', 'chaotic handheld long take', 'harsh tropical daylight', 'low angle in the dirt'],
    signature: ['Oner running with a mob', 'Night hunt lit by torches', 'Drone wide over paddy and forest'],
    knownFor: ['Angamaly Diaries', 'Jallikattu', 'Sarpatta Parambarai', 'Vikram Vedha', 'Churuli'],
  },
  {
    id: 'shyju-khalid', name: 'Shyju Khalid', region: 'India', era: '2010s to now',
    summary: 'Soft Kerala daylight, lived-in interiors, unforced handheld, green and ochre realism, humour left in the wide.',
    format: 'digital, natural light', aspectRatio: '2.39:1', lensCharacter: 'spherical', lensLadder: { wide: 25, normal: 40, long: 75 },
    lightingKey: 'natural', lightingQuality: 'soft', palette: ['#7a9b76', '#d9c8a9', '#4f4a41', '#a8b7c7'], colorTags: ['natural', 'green', 'muted', 'warm'],
    camera: 'mixed', depthOfField: 'mixed',
    styleVocabulary: ['soft Kerala daylight', 'lived-in domestic interior', 'unforced handheld', 'green and ochre realism', 'backwater light', 'quiet observational frame'],
    signature: ['Verandah two-shot with rain beyond', 'Wide of a house at dusk with lamps on', 'Boat on the backwaters at blue hour'],
    knownFor: ['Maheshinte Prathikaaram', 'Kumbalangi Nights', 'Ee.Ma.Yau', 'Joji', 'Sudani from Nigeria'],
  },
  {
    id: 'madhu-neelakandan', name: 'Madhu Neelakandan', region: 'India', era: '2010s to now',
    summary: 'Gentle daylight, romantic softness, green Kerala landscapes, restrained camera that lets period detail breathe.',
    format: 'digital', aspectRatio: '2.39:1', lensCharacter: 'spherical', lensLadder: { wide: 25, normal: 40, long: 75 },
    lightingKey: 'natural', lightingQuality: 'diffused', palette: ['#6f8f6a', '#e0cfa8', '#4d5560', '#2f2a26'], colorTags: ['green', 'muted', 'warm', 'sepia'],
    camera: 'fluid', depthOfField: 'mixed',
    styleVocabulary: ['gentle diffused daylight', 'romantic softness', 'lush green landscape', 'restrained camera', 'period detail in natural light', 'monsoon grey'],
    signature: ['Wide of a river under grey sky', 'Soft-lit face at a window', 'Slow dolly along a verandah'],
    knownFor: ['Ennu Ninte Moideen', 'Rani Padmini'],
  },
  {
    id: 'subrata-mitra', name: 'Subrata Mitra', region: 'India', era: '1950s to 1980s',
    summary: 'Bounce lighting invented on set, black and white tonal richness, rain and monsoon light, still contemplative frames.',
    format: '35mm black and white', aspectRatio: '4:3', lensCharacter: 'spherical', lensLadder: { wide: 35, normal: 50, long: 75 },
    lightingKey: 'natural', lightingQuality: 'diffused', palette: ['#111111', '#555555', '#aaaaaa', '#eeeeee'], colorTags: ['monochrome', 'low contrast', 'natural', 'muted'],
    camera: 'locked', depthOfField: 'deep',
    styleVocabulary: ['bounce-lit soft daylight', 'black and white tonal richness', 'monsoon rain light', 'still contemplative frame', 'daylight through a courtyard', 'neorealist village texture'],
    signature: ['Child running through wet paddy', 'Woman at a window in soft bounce light', 'Rain on a courtyard'],
    knownFor: ['Pather Panchali', 'Aparajito', 'Charulata', 'Jalsaghar', 'Nayak'],
  },
  {
    id: 'asakazu-nakai', name: 'Asakazu Nakai', region: 'Japan', era: '1940s to 1980s',
    summary: 'Long lenses in harsh sun, deep-black monochrome with rain and dust, multi-camera coverage of big action, later saturated colour for painted battlefields.',
    format: '35mm black and white, later colour', aspectRatio: '2.39:1', lensCharacter: 'telephoto', lensLadder: { wide: 50, normal: 100, long: 200 },
    lightingKey: 'harsh-sun', lightingQuality: 'hard', palette: ['#1a1a1a', '#8c8c8c', '#e8e2d0', '#b23a2a'], colorTags: ['high contrast', 'monochrome', 'earth tones', 'red accent'],
    camera: 'fluid', depthOfField: 'shallow',
    styleVocabulary: ['long lens compression', 'harsh sun with deep blacks', 'rain streaking through backlight', 'dust and smoke on a battlefield', 'monochrome tonal punch', 'telephoto crowd frieze'],
    signature: ['Rain-soaked battle on a 200mm', 'Riders compressed against a hill', 'Burning castle in saturated colour'],
    knownFor: ['Seven Samurai', 'Throne of Blood', 'High and Low', 'Ran', 'Ikiru'],
  },
  {
    id: 'kazuo-miyagawa', name: 'Kazuo Miyagawa', region: 'Japan', era: '1940s to 1980s',
    summary: 'Sun through forest leaves, tracking shots through woods, deep focus with foreground detail, painterly period light.',
    format: '35mm black and white', aspectRatio: '4:3', lensCharacter: 'spherical', lensLadder: { wide: 28, normal: 50, long: 85 },
    lightingKey: 'natural', lightingQuality: 'hard', palette: ['#111111', '#6a6a6a', '#d9d9d9', '#f5f5f5'], colorTags: ['monochrome', 'high contrast', 'natural'],
    camera: 'fluid', depthOfField: 'deep',
    styleVocabulary: ['sunlight flickering through leaves', 'tracking through forest', 'deep focus with foreground detail', 'mirror-bounced sunlight', 'painterly period monochrome', 'dust in a village street'],
    signature: ['Camera pointed at the sun through branches', 'Long track following a woodcutter', 'Wind blowing dust down an empty street'],
    knownFor: ['Rashomon', 'Ugetsu', 'Yojimbo', 'Sansho the Bailiff', 'Floating Weeds'],
  },
  {
    id: 'atsushi-okui', name: 'Atsushi Okui (Ghibli)', region: 'Japan', era: '1990s to now',
    summary: 'Animation photography: multi-plane depth on painted backgrounds, soft light through cel colour, gentle pans across watercolour skies, glow and haze on flight.',
    format: 'hand-drawn animation, multi-plane digital compositing', aspectRatio: '1.85:1', lensCharacter: 'spherical', lensLadder: { wide: 24, normal: 35, long: 50 },
    lightingKey: 'high-key', lightingQuality: 'soft', palette: ['#79b5e0', '#8fc07a', '#f2e6c9', '#4a3f3a'], colorTags: ['saturated', 'pastel', 'green', 'blue'],
    camera: 'fluid', depthOfField: 'deep',
    styleVocabulary: ['hand-painted watercolour background', 'multi-plane depth', 'soft cel-shaded light', 'gentle pan across sky', 'glow and haze on flight', 'clean line and flat colour'],
    signature: ['Slow pan across painted clouds', 'Multi-plane push through a forest', 'Warm lamplight in a painted kitchen'],
    knownFor: ['Spirited Away', "Howl's Moving Castle", 'Ponyo', 'The Wind Rises', 'The Boy and the Heron'],
  },
]

export const CUSTOM_DP: CinematographerProfile = {
  id: 'custom', name: 'Custom lensing', region: 'You', era: 'Now',
  summary: 'Describe the format, lenses, light and colour; the engine reads focal lengths, anamorphic, handheld, low key, neon and palette words from it.',
  format: '35mm spherical', aspectRatio: '2.39:1', lensCharacter: 'spherical', lensLadder: { wide: 24, normal: 40, long: 85 },
  lightingKey: 'natural', lightingQuality: 'soft', palette: ['#888888', '#444444', '#cccccc', '#222222'], colorTags: ['natural'],
  camera: 'fluid', depthOfField: 'mixed', styleVocabulary: [], signature: [], knownFor: [],
}

export const SAME_DP: CinematographerProfile = {
  ...CUSTOM_DP, id: 'same', name: "Director's usual DP", summary: 'Use the cinematographer this director usually works with, or lensing derived from the director profile when none is listed.',
}

export const ALL_CINEMATOGRAPHERS: CinematographerProfile[] = [SAME_DP, CUSTOM_DP, ...CINEMATOGRAPHERS]

export function getCinematographer(id: string): CinematographerProfile | undefined {
  return CINEMATOGRAPHERS.find((d) => d.id === id)
}

const customCache = new Map<string, CinematographerProfile>()
export function dpFromText(text: string): CinematographerProfile {
  const hit = customCache.get(text)
  if (hit) return hit
  const built = buildDpFromText(text)
  customCache.set(text, built)
  return built
}

function buildDpFromText(text: string): CinematographerProfile {
  const t = text.toLowerCase()
  const p: CinematographerProfile = { ...CUSTOM_DP, lensLadder: { ...CUSTOM_DP.lensLadder }, styleVocabulary: [] }
  if (/anamorphic/.test(t)) { p.lensCharacter = 'anamorphic'; p.format = '35mm anamorphic' }
  else if (/vintage|old glass|uncoated/.test(t)) p.lensCharacter = 'vintage'
  else if (/telephoto|long lens/.test(t)) p.lensCharacter = 'telephoto'
  else if (/wide lens|wide-angle|wide angle|ultra wide/.test(t)) p.lensCharacter = 'wide'
  if (/16 ?mm|super ?16/.test(t)) p.format = 'Super 16'
  else if (/65 ?mm|imax|large format/.test(t)) p.format = 'large format 65mm'
  else if (/digital|alexa|red |venice/.test(t)) p.format = p.lensCharacter === 'anamorphic' ? 'digital anamorphic' : 'digital'
  const mms = [...t.matchAll(/(\d{2,3})\s?mm/g)].map((m) => Number(m[1])).filter((n) => n >= 8 && n <= 400 && n !== 16 && n !== 35 && n !== 65).sort((a, b) => a - b)
  if (mms.length === 1) p.lensLadder = { wide: mms[0], normal: mms[0], long: mms[0] }
  else if (mms.length >= 2) p.lensLadder = { wide: mms[0], normal: mms[Math.floor(mms.length / 2)], long: mms[mms.length - 1] }
  if (/low[- ]key|dark|shadow|underexpos/.test(t)) p.lightingKey = 'low-key'
  else if (/neon/.test(t)) p.lightingKey = 'neon'
  else if (/golden|magic hour|backlight|backlit/.test(t)) { p.lightingKey = 'golden-hour'; p.lightingQuality = 'back-lit' }
  else if (/practical/.test(t)) p.lightingKey = 'practical'
  else if (/high[- ]key|bright|even/.test(t)) p.lightingKey = 'high-key'
  else if (/overcast|grey|gray/.test(t)) p.lightingKey = 'overcast'
  if (/hard light|hard shadow/.test(t)) p.lightingQuality = 'hard'
  if (/handheld/.test(t)) p.camera = 'handheld'
  else if (/locked|static|tripod/.test(t)) p.camera = 'locked'
  else if (/steadicam|dolly|gimbal/.test(t)) p.camera = 'fluid'
  if (/shallow/.test(t)) p.depthOfField = 'shallow'
  else if (/deep focus/.test(t)) p.depthOfField = 'deep'
  const tags = ['warm', 'cool', 'desaturated', 'saturated', 'monochrome', 'teal-orange', 'pastel', 'earth tones', 'amber', 'neon', 'golden', 'sepia', 'high contrast', 'low contrast', 'muted', 'green', 'blue', 'bleach bypass'].filter((x) => t.includes(x))
  if (tags.length) p.colorTags = tags
  if (/2\.39|scope|widescreen/.test(t)) p.aspectRatio = '2.39:1'
  else if (/4:3|academy/.test(t)) p.aspectRatio = '4:3'
  else if (/1\.85/.test(t)) p.aspectRatio = '1.85:1'
  else if (/16:9/.test(t)) p.aspectRatio = '16:9'
  const words = text.split(/[,.;\n]/).map((s) => s.trim()).filter((s) => s.length > 3 && s.length < 60)
  p.styleVocabulary = words.slice(0, 8)
  p.summary = text.trim() || CUSTOM_DP.summary
  return p
}
