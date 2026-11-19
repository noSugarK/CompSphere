import type { Me } from '../api/schemas';

export function mayViewCompetitionRegistry(me: Me | null) {
  return (
    me?.grants.some(
      (grant) =>
        grant.permissions.includes('competition:read') &&
        (grant.scope_type === 'competition' ||
          (grant.scope_type === 'global' && grant.role === 'platform_admin')),
    ) ?? false
  );
}

export function mayCreateCompetition(me: Me | null) {
  return (
    me?.grants.some(
      (grant) =>
        grant.role === 'platform_admin' &&
        grant.scope_type === 'global' &&
        grant.permissions.includes('competition:create'),
    ) ?? false
  );
}

export function mayCreateEdition(me: Me | null, competitionId: number) {
  return (
    me?.grants.some(
      (grant) =>
        grant.permissions.includes('edition:create') &&
        ((grant.role === 'platform_admin' && grant.scope_type === 'global') ||
          (grant.scope_type === 'competition' && grant.scope_id === competitionId)),
    ) ?? false
  );
}

export function hasPermission(me: Me | null, permission: string) {
  return me?.grants.some((grant) => grant.permissions.includes(permission)) ?? false;
}
export function mayEnter(me: Me | null, permissions: unknown) {
  return (
    !Array.isArray(permissions) ||
    permissions.some(
      (permission: unknown) => typeof permission === 'string' && hasPermission(me, permission),
    )
  );
}
export function mayRenderPrivate(authRequired: unknown, authenticated: boolean) {
  return !authRequired || authenticated;
}
