const STEAM_OPENID_URL = 'https://steamcommunity.com/openid/login'

/**
 * Build the URL that sends the user to Steam to authenticate.
 * `realm` is the base origin of our site, `returnTo` is our callback endpoint.
 */
export function buildSteamAuthUrl(realm: string, returnTo: string): string {
  const params = new URLSearchParams({
    'openid.ns': 'http://specs.openid.net/auth/2.0',
    'openid.mode': 'checkid_setup',
    'openid.return_to': returnTo,
    'openid.realm': realm,
    'openid.identity': 'http://specs.openid.net/auth/2.0/identifier_select',
    'openid.claimed_id': 'http://specs.openid.net/auth/2.0/identifier_select',
  })
  return `${STEAM_OPENID_URL}?${params.toString()}`
}

/**
 * Verify the OpenID response coming back from Steam by asking Steam to
 * confirm the assertion (check_authentication). Returns the 64-bit SteamID.
 */
export async function verifySteamCallback(query: URLSearchParams): Promise<string | null> {
  const claimedId = query.get('openid.claimed_id')
  if (!claimedId) return null

  const body = new URLSearchParams()
  query.forEach((value, key) => {
    if (key.startsWith('openid.')) body.append(key, value)
  })
  body.set('openid.mode', 'check_authentication')

  const res = await fetch(STEAM_OPENID_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  })
  const text = await res.text()
  if (!/is_valid\s*:\s*true/i.test(text)) return null

  const match = claimedId.match(/\/openid\/id\/(\d+)$/)
  return match ? match[1] : null
}

export type SteamProfile = {
  steamId: string
  personaName: string
  avatar: string
  profileUrl: string
}

/**
 * Fetch the player's public profile. Requires STEAM_API_KEY.
 * Falls back to a minimal profile if the key is missing or the call fails.
 */
export async function fetchSteamProfile(steamId: string): Promise<SteamProfile> {
  const key = process.env.STEAM_API_KEY
  const fallback: SteamProfile = {
    steamId,
    personaName: `Player ${steamId.slice(-4)}`,
    avatar: '',
    profileUrl: `https://steamcommunity.com/profiles/${steamId}`,
  }
  if (!key) return fallback

  try {
    const res = await fetch(
      `https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/?key=${key}&steamids=${steamId}`,
      { cache: 'no-store' },
    )
    if (!res.ok) return fallback
    const data = await res.json()
    const player = data?.response?.players?.[0]
    if (!player) return fallback
    return {
      steamId,
      personaName: player.personaname ?? fallback.personaName,
      avatar: player.avatarfull ?? '',
      profileUrl: player.profileurl ?? fallback.profileUrl,
    }
  } catch {
    return fallback
  }
}
