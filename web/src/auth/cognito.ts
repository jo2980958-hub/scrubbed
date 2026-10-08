import { COGNITO_CLIENT_ID, COGNITO_REGION } from '../config';

/**
 * Minimal Cognito client over the public Identity Provider JSON API, so the
 * bundle needs no AWS SDK. Requires an app client (no secret) with
 * ALLOW_USER_PASSWORD_AUTH and ALLOW_REFRESH_TOKEN_AUTH enabled.
 */

export interface Session {
  idToken: string;
  accessToken: string;
  refreshToken: string;
  /** epoch ms */
  expiresAt: number;
  email: string;
}

export type SignInResult =
  | { kind: 'session'; session: Session }
  | { kind: 'new_password'; challengeSession: string; username: string };

export class AuthError extends Error {}

const endpoint = () => `https://cognito-idp.${COGNITO_REGION}.amazonaws.com/`;

async function call<T>(target: string, body: unknown): Promise<T> {
  if (!COGNITO_CLIENT_ID) throw new AuthError('Sign-in is not configured (VITE_COGNITO_CLIENT_ID is empty).');
  let res: Response;
  try {
    res = await fetch(endpoint(), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-amz-json-1.1',
        'X-Amz-Target': `AWSCognitoIdentityProviderService.${target}`,
      },
      body: JSON.stringify(body),
    });
  } catch {
    throw new AuthError("Can't reach the sign-in service. Check your connection.");
  }
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new AuthError(friendly(json.__type, json.message));
  return json as T;
}

function friendly(type?: string, message?: string): string {
  switch (type) {
    case 'NotAuthorizedException':
    case 'UserNotFoundException':
      return 'That email and password do not match. Check them and try again.';
    case 'UserNotConfirmedException':
      return 'This account has not been confirmed yet. Check your email for the confirmation link.';
    case 'PasswordResetRequiredException':
      return 'You need to reset your password before signing in.';
    case 'InvalidPasswordException':
      return message ?? 'That password does not meet the requirements.';
    case 'TooManyRequestsException':
    case 'LimitExceededException':
      return 'Too many attempts. Wait a minute and try again.';
    default:
      return message ?? 'Something went wrong signing you in.';
  }
}

interface AuthResult {
  IdToken: string;
  AccessToken: string;
  RefreshToken?: string;
  ExpiresIn: number;
}

function toSession(r: AuthResult, email: string, prevRefresh?: string): Session {
  return {
    idToken: r.IdToken,
    accessToken: r.AccessToken,
    refreshToken: r.RefreshToken ?? prevRefresh ?? '',
    expiresAt: Date.now() + r.ExpiresIn * 1000,
    email,
  };
}

export async function signIn(email: string, password: string): Promise<SignInResult> {
  const r = await call<{ AuthenticationResult?: AuthResult; ChallengeName?: string; Session?: string }>('InitiateAuth', {
    AuthFlow: 'USER_PASSWORD_AUTH',
    ClientId: COGNITO_CLIENT_ID,
    AuthParameters: { USERNAME: email, PASSWORD: password },
  });
  if (r.AuthenticationResult) return { kind: 'session', session: toSession(r.AuthenticationResult, email) };
  if (r.ChallengeName === 'NEW_PASSWORD_REQUIRED' && r.Session) {
    return { kind: 'new_password', challengeSession: r.Session, username: email };
  }
  throw new AuthError('This account needs an extra sign-in step that this app does not support yet.');
}

export async function completeNewPassword(username: string, newPassword: string, challengeSession: string): Promise<Session> {
  const r = await call<{ AuthenticationResult: AuthResult }>('RespondToAuthChallenge', {
    ChallengeName: 'NEW_PASSWORD_REQUIRED',
    ClientId: COGNITO_CLIENT_ID,
    Session: challengeSession,
    ChallengeResponses: { USERNAME: username, NEW_PASSWORD: newPassword },
  });
  return toSession(r.AuthenticationResult, username);
}

export async function refresh(s: Session): Promise<Session> {
  const r = await call<{ AuthenticationResult: AuthResult }>('InitiateAuth', {
    AuthFlow: 'REFRESH_TOKEN_AUTH',
    ClientId: COGNITO_CLIENT_ID,
    AuthParameters: { REFRESH_TOKEN: s.refreshToken },
  });
  return toSession(r.AuthenticationResult, s.email, s.refreshToken);
}

/* ------------------------------------------------------------- persistence */

const KEY = 'scrubbed.session.v1';

export function loadSession(): Session | null {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

export function saveSession(s: Session | null) {
  try {
    if (s) localStorage.setItem(KEY, JSON.stringify(s));
    else localStorage.removeItem(KEY);
  } catch {
    /* storage unavailable: session lives in memory only */
  }
}
