// ─────────────────── Validators ───────────────────

export function validateEmail(email: string): boolean {
  const regex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
  return regex.test(email);
}

export function getEmailError(email: string): string | null {
  if (!email) return '请输入邮箱地址';
  if (!validateEmail(email)) return '请输入有效的邮箱地址';
  return null;
}

export function validatePassword(password: string): {
  isValid: boolean;
  strength: 'weak' | 'medium' | 'strong';
  errors: string[];
} {
  const errors: string[] = [];
  if (!password || password.length < 8) errors.push('密码长度至少8位');
  if (!/[A-Z]/.test(password)) errors.push('需包含大写字母');
  if (!/[a-z]/.test(password)) errors.push('需包含小写字母');
  if (!/[0-9]/.test(password)) errors.push('需包含数字');
  if (!/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password)) {
    errors.push('需包含特殊字符');
  }

  const isValid = errors.length === 0;
  let strength: 'weak' | 'medium' | 'strong' = 'weak';
  if (password.length >= 12 && /[A-Z]/.test(password) && /[a-z]/.test(password)
      && /[0-9]/.test(password) && /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password)) {
    strength = 'strong';
  } else if (password.length >= 8 && errors.length <= 2) {
    strength = 'medium';
  }

  return { isValid, strength, errors };
}

export function validateStockCode(code: string): boolean {
  return /^\d{6}$/.test(code);
}

export function getStockCodeError(code: string): string | null {
  if (!code) return '请输入股票代码';
  if (!validateStockCode(code)) return '股票代码必须为6位数字';
  return null;
}

export function validatePasswordMatch(password: string, confirmPassword: string): boolean {
  return password === confirmPassword && confirmPassword.length > 0;
}

export function getPasswordMatchError(password: string, confirmPassword: string): string | null {
  if (!confirmPassword) return '请确认密码';
  if (password !== confirmPassword) return '两次输入的密码不一致';
  return null;
}

export function validateRequired(value: string, fieldName = '该字段'): string | null {
  if (!value || value.trim().length === 0) return `${fieldName}不能为空`;
  return null;
}

export function validateRange(value: number, min: number, max: number, fieldName = '该字段'): string | null {
  if (value < min) return `${fieldName}不能小于 ${min}`;
  if (value > max) return `${fieldName}不能大于 ${max}`;
  return null;
}

export function validateDateRange(startDate: string, endDate: string): string | null {
  if (!startDate || !endDate) return null;
  const start = new Date(startDate);
  const end = new Date(endDate);
  if (start > end) return '开始日期不能晚于结束日期';
  return null;
}

export function validateSymbolList(symbols: string): string | null {
  const list = symbols.split(/[,\s]+/).filter(Boolean);
  if (list.length === 0) return '请输入至少一个股票代码';
  for (const s of list) {
    if (!validateStockCode(s)) return `无效的代码: ${s}`;
  }
  return null;
}
