import { ZodError } from 'zod';
import { ApiError } from '../api/client';
import { i18n } from '../locales';

export function errorMessage(error: unknown) {
  const t = i18n.global.t;
  if (error instanceof ZodError) return t('fieldError');
  if (!(error instanceof ApiError)) return t('unknownError');
  const messages: Record<number, string> = {
    40001: 'fieldError',
    40101: 'unauthorized',
    40102: 'verificationInvalid',
    40105: 'loginInvalid',
    40301: 'noAccess',
    40303: 'selfReview',
    40304: 'restricted',
    40401: 'notFound',
    40901: 'duplicateRegistration',
    40902: 'statusConflict',
    40903: 'rosterLocked',
    40904: 'identityConflict',
    40905: 'idempotencyConflict',
    40906: 'versionConflict',
    40907: 'teamConflict',
    40908: 'teamConflict',
    40909: 'teamConflict',
    40910: 'licenseMissing',
    40911: 'seasonUnavailable',
    42201: 'memberCountInvalid',
    42202: 'filePending',
    42203: 'windowClosed',
    42204: 'eligibilityInvalid',
    42205: 'eligibilityInvalid',
    42206: 'documentInvalid',
    42207: 'offeringUnavailable',
    42208: 'coachRequired',
    42211: 'teamNotReviewed',
    42212: 'noAccess',
    42213: 'orgNotReviewed',
    42901: 'rateLimited',
    50201: 'invalidResponse',
    50301: 'unavailable',
  };
  return t(messages[error.code] || 'unknownError');
}
