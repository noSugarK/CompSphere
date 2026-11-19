import { z } from 'zod';
import { idSchema } from './schemas';
import type { components } from './generated';

export const emailSchema = z.string().trim().toLowerCase().email().max(255);
export const verificationCodeSchema = z.string().regex(/^[0-9]{6}$/);
const newPasswordSchema = z.string().min(12).max(256);
export const verificationRequestSchema = z
  .object({ email: emailSchema, purpose: z.enum(['register', 'reset_password']) })
  .strict();
export const registerRequestSchema = z
  .object({
    email: emailSchema,
    password: newPasswordSchema,
    verification_code: verificationCodeSchema,
    real_name: z.string().trim().min(1).max(64),
  })
  .strict();
export const resetPasswordRequestSchema = z
  .object({
    email: emailSchema,
    verification_code: verificationCodeSchema,
    new_password: newPasswordSchema,
  })
  .strict();
export const registerResultSchema = z
  .object({ id: idSchema, status: z.literal('active') })
  .strict();

export const checkedAccountContractSchemas = {
  verification: verificationRequestSchema,
  register: registerRequestSchema,
  reset: resetPasswordRequestSchema,
  registered: registerResultSchema,
} satisfies {
  verification: z.ZodType<components['schemas']['VerificationRequestRequest']>;
  register: z.ZodType<components['schemas']['RegisterRequest']>;
  reset: z.ZodType<components['schemas']['PasswordResetRequest']>;
  registered: z.ZodType<components['schemas']['RegisteredAccount']>;
};
