import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from 'react';
import { AlertCircle, BookOpen, LoaderCircle } from 'lucide-react';

export function Button({ variant = 'primary', className = '', type = 'button', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'outline' }) {
  return <button type={type} className={`btn btn-${variant} ${className}`} {...props} />;
}

export function Input({ label, id, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string; id: string }) {
  return <div className="field"><label htmlFor={id}>{label}</label><input id={id} className="input-field" {...props} /></div>;
}

export function LoadingState({ message = 'Đang tải dữ liệu…' }: { message?: string }) {
  return <div className="state-panel" role="status" aria-live="polite"><LoaderCircle className="spinner" aria-hidden="true" /><p>{message}</p></div>;
}

export function EmptyState({ title = 'Chưa có kết quả', children, action }: { title?: string; children?: ReactNode; action?: ReactNode }) {
  return <div className="state-panel" role="status"><BookOpen aria-hidden="true" /><h2>{title}</h2>{children && <p>{children}</p>}{action}</div>;
}

export function ErrorState({ message = 'Chưa tải được dữ liệu. Bạn có thể thử lại.', onRetry }: { message?: string; onRetry: () => void }) {
  return <div className="state-panel error-panel" role="alert"><AlertCircle aria-hidden="true" /><h2>Chưa tải được dữ liệu</h2><p>{message}</p><Button variant="outline" onClick={onRetry}>Thử lại</Button></div>;
}
