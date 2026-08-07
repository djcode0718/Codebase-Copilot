/**
 * frontend/lib/auth-recovery-utils.ts
 * Shared utilities for password recovery flow
 */

import { toast } from 'sonner';

export function validatePasswordForReset(password: string) {
  if (!password.trim()) {
    return { valid: false, error: 'Password is required.' };
  }
  if (password.length < 8) {
    return { valid: false, error: 'Use at least 8 characters for your new password.' };
  }
  return { valid: true };
}

export function validatePasswordsMatch(password: string, confirmPassword: string) {
  if (!confirmPassword.trim()) {
    return { valid: false, error: 'Please confirm your password.' };
  }
  if (password !== confirmPassword) {
    return { valid: false, error: 'Passwords do not match.' };
  }
  return { valid: true };
}

export function validateEmailForRecovery(email: string) {
  if (!email.trim()) {
    return { valid: false, error: 'Email is required.' };
  }
  if (!/^\S+@\S+\.\S+$/.test(email)) {
    return { valid: false, error: 'Enter a valid email address.' };
  }
  return { valid: true };
}

export function getPasswordResetRedirectUrl() {
  if (typeof window === 'undefined') return '';
  return `${window.location.origin}/auth/reset-password`;
}

export function showPasswordRecoveryError(context: 'forgot' | 'reset') {
  const message =
    context === 'forgot'
      ? 'Unable to start password reset right now. Please try again.'
      : 'Unable to update password. Request a new reset link and try again.';
  toast.error(message);
}
