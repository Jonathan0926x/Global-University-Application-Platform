/**
 * Authentication Provider Abstraction (Client-Side)
 * Decouples frontend authentication from specific vendor implementations (Clerk vs. Mock/Self-hosted).
 */

export interface AuthUser {
  id: string;
  email: string;
  firstName?: string;
  lastName?: string;
  role: string;
}

export interface AuthSession {
  isAuthenticated: boolean;
  user: AuthUser | null;
  token: string | null;
}

// Default development session when Clerk keys are not configured
export const mockDevSession: AuthSession = {
  isAuthenticated: true,
  user: {
    id: "user_dev_123",
    email: "dev.student@uniglobe.edu",
    firstName: "Jordan",
    lastName: "Taylor",
    role: "student",
  },
  token: "Bearer dev_token",
};

export class AuthManager {
  private static instance: AuthManager;
  private providerType: "clerk" | "mock" = "mock";

  private constructor() {
    if (process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY) {
      this.providerType = "clerk";
    }
  }

  public static getInstance(): AuthManager {
    if (!AuthManager.instance) {
      AuthManager.instance = new AuthManager();
    }
    return AuthManager.instance;
  }

  public getSession(): AuthSession {
    if (this.providerType === "clerk") {
      // In Clerk mode, would retrieve token from Clerk window / cookie session
      return mockDevSession;
    }
    return mockDevSession;
  }

  public getAuthHeader(): Record<string, string> {
    const session = this.getSession();
    return session.token ? { Authorization: session.token } : {};
  }
}

export const auth = AuthManager.getInstance();
