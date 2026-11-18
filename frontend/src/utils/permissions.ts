import type { Me } from '../api/schemas';

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
