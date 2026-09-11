// src/app/core/store/index.ts
export { initializeStore, getUseStore, useStore as useStoreProxy } from './initializer';
export type { RootState } from './types';
export { default as useStore, default } from './initializer';