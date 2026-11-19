import { createRouter, createWebHistory } from 'vue-router';
import { useSession } from '../stores/session';
import { i18n } from '../locales';
import { mayEnter, mayViewCompetitionRegistry } from '../utils/permissions';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'discover',
      component: () => import('../views/DiscoverView.vue'),
      meta: { title: 'discover' },
    },
    {
      path: '/season-management',
      name: 'seasonManagement',
      component: () => import('../views/SeasonManagementView.vue'),
      meta: { title: 'seasonManagement', auth: true, permissions: ['season:read'] },
    },
    {
      path: '/competition-registry',
      name: 'competitionRegistry',
      component: () => import('../views/CompetitionRegistryView.vue'),
      meta: { title: 'competitionRegistry', auth: true, competitionRegistry: true },
    },
    {
      path: '/competition-registry/:id/editions',
      name: 'editionRegistry',
      component: () => import('../views/EditionRegistryView.vue'),
      meta: { title: 'editionRegistry', auth: true, permissions: ['edition:read'] },
    },
    {
      path: '/edition-config/:id',
      name: 'editionConfig',
      component: () => import('../views/EditionConfigurationView.vue'),
      meta: { title: 'editionConfiguration', auth: true, permissions: ['event:read'] },
    },
    {
      path: '/editions/:id',
      name: 'edition',
      component: () => import('../views/EditionView.vue'),
      meta: { title: 'details' },
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { title: 'login' },
    },
    {
      path: '/password',
      name: 'password',
      component: () => import('../views/PasswordView.vue'),
      meta: { title: 'changePassword', auth: true },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('../views/EmailAccountView.vue'),
      meta: { title: 'register' },
    },
    {
      path: '/password-reset',
      name: 'password-reset',
      component: () => import('../views/EmailAccountView.vue'),
      meta: { title: 'forgotPassword' },
    },
    {
      path: '/teams',
      name: 'teams',
      component: () => import('../views/TeamsView.vue'),
      meta: { title: 'teams', auth: true, permissions: ['team:read', 'team:leave_own'] },
    },
    {
      path: '/team-requests',
      name: 'requests',
      component: () => import('../views/TeamRequestsView.vue'),
      meta: {
        title: 'requests',
        auth: true,
        permissions: ['team:create', 'team:review_create', 'team:review'],
      },
    },
    {
      path: '/season-licenses',
      name: 'licenses',
      component: () => import('../views/LicensesView.vue'),
      meta: {
        title: 'licenses',
        auth: true,
        permissions: ['team:request_season_registration', 'team:review_season_registration'],
      },
    },
    {
      path: '/notifications',
      name: 'notifications',
      component: () => import('../views/NotificationsView.vue'),
      meta: { title: 'notifications', auth: true },
    },
    {
      path: '/registrations',
      name: 'registrations',
      component: () => import('../views/RegistrationsView.vue'),
      meta: {
        title: 'registrations',
        auth: true,
        permissions: ['registration:read_own', 'registration:read'],
      },
    },
    {
      path: '/reviews',
      name: 'reviews',
      component: () => import('../views/RegistrationsView.vue'),
      meta: { title: 'reviews', auth: true, permissions: ['approval:review_single'] },
    },
    {
      path: '/registrations/new/:editionId',
      name: 'registration-new',
      component: () => import('../views/RegistrationView.vue'),
      meta: { title: 'enroll', auth: true, permissions: ['registration:create'] },
    },
    {
      path: '/registrations/:id',
      name: 'registration',
      component: () => import('../views/RegistrationView.vue'),
      meta: {
        title: 'details',
        auth: true,
        permissions: ['registration:read_own', 'registration:read'],
      },
    },
    {
      path: '/forbidden',
      name: 'forbidden',
      component: () => import('../views/ForbiddenView.vue'),
      meta: { title: 'forbiddenTitle' },
    },
    { path: '/:pathMatch(.*)*', redirect: '/forbidden' },
  ],
});
router.beforeEach(async (to) => {
  const session = useSession();
  await session.initialize();
  if (to.meta.auth && !session.authenticated)
    return { name: 'login', query: { next: to.fullPath } };
  if (session.me?.user.must_change_password && to.meta.auth && to.name !== 'password')
    return { name: 'password' };
  const permissions = to.meta.permissions;
  if (to.meta.competitionRegistry && !mayViewCompetitionRegistry(session.me))
    return { name: 'forbidden' };
  if (!mayEnter(session.me, permissions)) return { name: 'forbidden' };
});
router.afterEach(async (to) => {
  document.title = `${i18n.global.t(typeof to.meta.title === 'string' ? to.meta.title : 'app')} · ${i18n.global.t('app')}`;
  await Promise.resolve();
  document.querySelector<HTMLElement>('#page-title')?.focus({ preventScroll: true });
});
