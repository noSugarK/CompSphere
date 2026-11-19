import { describe, expect, it } from 'vitest';
import {
  registerRequestSchema,
  registerResultSchema,
  resetPasswordRequestSchema,
  verificationCodeSchema,
  verificationRequestSchema,
} from '../src/api/authSchemas';

const valid = {
  email: ' STUDENT@EXAMPLE.COM ',
  password: 'sufficiently-long-passphrase',
  verification_code: '001234',
  real_name: ' 林知远 ',
};
describe('email account request boundaries', () => {
  it('preserves leading zeroes and normalizes only identifiers and names', () => {
    const request = registerRequestSchema.parse(valid);
    expect(request.email).toBe('student@example.com');
    expect(request.real_name).toBe('林知远');
    expect(request.verification_code).toBe('001234');
  });
  it.each([123456, '１２３４５６', '12345', '1234567', '123 45', true, null])(
    'rejects non-ASCII or non-string code %s',
    (code) => {
      expect(verificationCodeSchema.safeParse(code).success).toBe(false);
    },
  );
  it('rejects injected grants and fields from a different operation', () => {
    expect(registerRequestSchema.safeParse({ ...valid, role: 'platform_admin' }).success).toBe(
      false,
    );
    expect(registerRequestSchema.safeParse({ ...valid, scope_id: 1 }).success).toBe(false);
    expect(
      resetPasswordRequestSchema.safeParse({
        email: valid.email,
        verification_code: valid.verification_code,
        new_password: valid.password,
        real_name: 'irrelevant',
      }).success,
    ).toBe(false);
    expect(
      verificationRequestSchema.safeParse({ email: valid.email, purpose: 'change_email' }).success,
    ).toBe(false);
  });
  it('rejects blank names, oversize inputs and short passwords', () => {
    expect(registerRequestSchema.safeParse({ ...valid, real_name: '  ' }).success).toBe(false);
    expect(registerRequestSchema.safeParse({ ...valid, real_name: '字'.repeat(65) }).success).toBe(
      false,
    );
    expect(registerRequestSchema.safeParse({ ...valid, password: 'short' }).success).toBe(false);
    expect(registerRequestSchema.safeParse({ ...valid, password: 'x'.repeat(257) }).success).toBe(
      false,
    );
  });
  it('never accepts credentials or a fake role in registration result', () => {
    expect(
      registerResultSchema.safeParse({ id: 1, status: 'active', access: 'unexpected' }).success,
    ).toBe(false);
    expect(registerResultSchema.safeParse({ id: '1', status: 'active' }).success).toBe(false);
    expect(registerResultSchema.parse({ id: 1, status: 'active' })).toEqual({
      id: 1,
      status: 'active',
    });
  });
});
