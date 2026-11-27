import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  getAuthMeV1AuthMeGetQueryKey,
  useAuthGoogleV1AuthGooglePost,
  useAuthLogoutV1AuthLogoutPost,
  useAuthMeV1AuthMeGet,
} from '../api/generated/auth/auth';
import { getListProjectsV1ProjectsGetQueryKey } from '../api/generated/projects/projects';
import { NapdaApiError, setAccessToken } from '../api/mutator';
import { AuthContext, type AuthContextValue, type AuthStatus } from './authContext';
import { getGoogleClientId, initializeGis } from './gis';

export interface AuthProviderProps {
  children: ReactNode;
  clientId?: string;
  enableOneTap?: boolean;
}

export function AuthProvider({
  children,
  clientId = getGoogleClientId(),
  enableOneTap = true,
}: AuthProviderProps) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [signedOutOverride, setSignedOutOverride] = useState(false);

  const meQuery = useAuthMeV1AuthMeGet({
    query: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  });

  const googleMutation = useAuthGoogleV1AuthGooglePost();
  const logoutMutation = useAuthLogoutV1AuthLogoutPost();

  const status: AuthStatus = signedOutOverride
    ? 'unauthenticated'
    : meQuery.isPending
      ? 'loading'
      : meQuery.isSuccess && meQuery.data.status === 200
        ? 'authenticated'
        : 'unauthenticated';

  const user =
    status === 'authenticated' && meQuery.data?.status === 200
      ? meQuery.data.data.user
      : null;

  const quota =
    status === 'authenticated' && meQuery.data?.status === 200
      ? meQuery.data.data.quota
      : null;

  const signInWithCredential = useCallback(
    async (credential: string) => {
      setError(null);
      setSignedOutOverride(false);
      try {
        const res = await googleMutation.mutateAsync({ data: { credential } });
        if (res.status === 200) {
          setAccessToken(res.data.access_token);
          queryClient.setQueryData(getAuthMeV1AuthMeGetQueryKey(), {
            data: { user: res.data.user, quota: res.data.quota },
            status: 200,
            headers: res.headers,
          });
          void queryClient.invalidateQueries({
            queryKey: getListProjectsV1ProjectsGetQueryKey(),
          });
        }
      } catch (err) {
        const msg =
          err instanceof NapdaApiError
            ? err.message
            : '구글 로그인에 실패했어요. 다시 시도해 주세요.';
        setError(msg);
      }
    },
    [googleMutation, queryClient],
  );

  const logout = useCallback(async () => {
    setError(null);
    setSignedOutOverride(true);
    setAccessToken(undefined);
    window.google?.accounts?.id?.disableAutoSelect();
    await queryClient.cancelQueries({ queryKey: getAuthMeV1AuthMeGetQueryKey() });
    try {
      await logoutMutation.mutateAsync();
    } catch {
      // Clear client session state even if the server cookie is already gone.
    } finally {
      queryClient.removeQueries({ queryKey: getAuthMeV1AuthMeGetQueryKey() });
      queryClient.removeQueries({ queryKey: getListProjectsV1ProjectsGetQueryKey() });
    }
  }, [logoutMutation, queryClient]);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  useEffect(() => {
    if (!enableOneTap || !clientId || status !== 'unauthenticated') {
      return;
    }

    let cancelled = false;
    void initializeGis(clientId, (credential) => {
      void signInWithCredential(credential);
    })
      .then((gis) => {
        if (!cancelled) {
          gis.prompt();
        }
      })
      .catch(() => {
        // One Tap is progressive enhancement; button component surfaces load issues.
      });

    return () => {
      cancelled = true;
      window.google?.accounts?.id?.cancel();
    };
  }, [clientId, enableOneTap, signInWithCredential, status]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      quota,
      isSubmitting: googleMutation.isPending || logoutMutation.isPending,
      error,
      clientId,
      signInWithCredential,
      logout,
      clearError,
    }),
    [
      clearError,
      clientId,
      error,
      googleMutation.isPending,
      logout,
      logoutMutation.isPending,
      quota,
      signInWithCredential,
      status,
      user,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
