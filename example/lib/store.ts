// In-memory demo store. For production, swap this for a real database
// (Neon is recommended) so duels and balances persist across instances.

export type Player = {
  steamId: string
  name: string
  avatar: string
}

export type DuelMode = 'Aim' | '1v1 Arena' | 'Retake' | 'Pistol Only' | 'AWP Only'
export type DuelStatus = 'open' | 'live' | 'finished'

export type Duel = {
  id: string
  mode: DuelMode
  map: string
  stake: number
  region: string
  status: DuelStatus
  createdAt: number
  creator: Player
  opponent: Player | null
  winnerSteamId: string | null
  scoreCreator: number
  scoreOpponent: number
}

type Store = {
  duels: Duel[]
}

const g = globalThis as unknown as { __duelzone?: Store }

function seed(): Duel[] {
  const bots: Player[] = [
    { steamId: 'bot-1', name: 'sh1ft_', avatar: '' },
    { steamId: 'bot-2', name: 'NoScopeKing', avatar: '' },
    { steamId: 'bot-3', name: 'entryFragger', avatar: '' },
    { steamId: 'bot-4', name: 'clutch_or_kick', avatar: '' },
    { steamId: 'bot-5', name: 'wallbang.exe', avatar: '' },
  ]
  const maps = ['Dust II', 'Mirage', 'Inferno', 'Nuke', 'Ancient']
  const modes: DuelMode[] = ['Aim', '1v1 Arena', 'Retake', 'Pistol Only', 'AWP Only']
  const regions = ['EU West', 'NA East', 'EU North', 'NA West']
  const stakes = [50, 100, 250, 500, 1000]

  return bots.map((creator, i) => ({
    id: `seed-${i + 1}`,
    mode: modes[i % modes.length],
    map: maps[i % maps.length],
    stake: stakes[i % stakes.length],
    region: regions[i % regions.length],
    status: 'open' as DuelStatus,
    createdAt: Date.now() - i * 60000,
    creator,
    opponent: null,
    winnerSteamId: null,
    scoreCreator: 0,
    scoreOpponent: 0,
  }))
}

function getStore(): Store {
  if (!g.__duelzone) {
    g.__duelzone = { duels: seed() }
  }
  return g.__duelzone
}

export function listDuels(): Duel[] {
  return [...getStore().duels].sort((a, b) => b.createdAt - a.createdAt)
}

export function getDuel(id: string): Duel | undefined {
  return getStore().duels.find((d) => d.id === id)
}

export function addDuel(duel: Duel): void {
  getStore().duels.unshift(duel)
}

export function updateDuel(id: string, patch: Partial<Duel>): Duel | undefined {
  const duel = getDuel(id)
  if (!duel) return undefined
  Object.assign(duel, patch)
  return duel
}
