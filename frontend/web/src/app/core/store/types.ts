// src/app/core/store/types.ts
import { AuthState } from './slices/auth.slice';
import { CoreState } from './slices/core.slice';
import { PermissionsState } from './slices/permissions.slice';

// Модульные слайсы импортируются динамически через pluginRegistry
// Тип RootState расширяется через intersection с модульными состояниями
export interface RootState extends CoreState, AuthState, PermissionsState {
  // Динамические слайсы добавляются через pluginRegistry
  // TypeScript не может статически типизировать динамические ключи,
  // поэтому используем index signature для совместимости
  [key: string]: any;
}
