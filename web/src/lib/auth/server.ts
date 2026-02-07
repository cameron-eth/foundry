import { createAuthServer, authApiHandler } from '@neondatabase/auth/next/server';

export const auth = createAuthServer();

export const handler = authApiHandler();
