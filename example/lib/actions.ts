'use server'

import { revalidatePath } from 'next/cache'
import { redirect } from 'next/navigation'
import { getSession, setSession } from '@/lib/session'
import { addDuel, getDuel, updateDuel, type Duel, type DuelMode } from '@/lib/store'

export type ActionResult = { error?: string }

function newId(): string {
  return `d-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`
}

export async function createDuel(_prev: ActionResult, formData: FormData): Promise<ActionResult> {
  const session = await getSession()
  if (!session) return { error: 'You must sign in through Steam first.' }

  const mode = String(formData.get('mode') || 'Aim') as DuelMode
  const map = String(formData.get('map') || 'Dust II')
  const region = String(formData.get('region') || 'EU West')
  const stake = Number(formData.get('stake') || 0)

  if (!Number.isFinite(stake) || stake <= 0) return { error: 'Enter a valid stake amount.' }
  if (stake > session.balance) return { error: 'Insufficient balance for this stake.' }

  const duel: Duel = {
    id: newId(),
    mode,
    map,
    region,
    stake,
    status: 'open',
    createdAt: Date.now(),
    creator: { steamId: session.steamId, name: session.personaName, avatar: session.avatar },
    opponent: null,
    winnerSteamId: null,
    scoreCreator: 0,
    scoreOpponent: 0,
  }
  addDuel(duel)
  await setSession({ ...session, balance: session.balance - stake })

  revalidatePath('/lobby')
  redirect(`/match/${duel.id}`)
}

export async function joinDuel(id: string): Promise<ActionResult> {
  const session = await getSession()
  if (!session) return { error: 'You must sign in through Steam first.' }

  const duel = getDuel(id)
  if (!duel) return { error: 'Duel not found.' }
  if (duel.status !== 'open') return { error: 'This duel is no longer open.' }
  if (duel.creator.steamId === session.steamId) return { error: 'You cannot join your own duel.' }
  if (duel.stake > session.balance) return { error: 'Insufficient balance to join.' }

  updateDuel(id, {
    status: 'live',
    opponent: { steamId: session.steamId, name: session.personaName, avatar: session.avatar },
  })
  await setSession({ ...session, balance: session.balance - duel.stake })

  revalidatePath('/lobby')
  redirect(`/match/${id}`)
}

/**
 * Demo-only resolver that settles a live match and pays the pot to the winner.
 * In production this would be driven by verified match results from the game server.
 */
export async function resolveMatch(id: string, winner: 'creator' | 'opponent'): Promise<ActionResult> {
  const session = await getSession()
  if (!session) return { error: 'Not signed in.' }
  const duel = getDuel(id)
  if (!duel || duel.status !== 'live' || !duel.opponent) return { error: 'Match cannot be resolved.' }

  const winnerPlayer = winner === 'creator' ? duel.creator : duel.opponent
  const pot = duel.stake * 2
  updateDuel(id, {
    status: 'finished',
    winnerSteamId: winnerPlayer.steamId,
    scoreCreator: winner === 'creator' ? 16 : Math.floor(Math.random() * 15),
    scoreOpponent: winner === 'opponent' ? 16 : Math.floor(Math.random() * 15),
  })

  // Pay out the pot if the signed-in user is the winner (demo settlement).
  if (winnerPlayer.steamId === session.steamId) {
    await setSession({ ...session, balance: session.balance + pot })
  }

  revalidatePath(`/match/${id}`)
  revalidatePath('/lobby')
  return {}
}

export async function topUp(_prev: ActionResult, formData: FormData): Promise<ActionResult> {
  const session = await getSession()
  if (!session) return { error: 'You must sign in through Steam first.' }
  const amount = Number(formData.get('amount') || 0)
  if (!Number.isFinite(amount) || amount <= 0) return { error: 'Enter a valid amount.' }

  await setSession({ ...session, balance: session.balance + amount })
  revalidatePath('/wallet')
  return {}
}
