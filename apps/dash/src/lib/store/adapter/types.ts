import type { SchemaDefinition, StoreSnapshot } from "../schema/types";

/**
 * Store adapter interface that all adapters must implement
 */
export interface StoreAdapter<T extends Record<string, unknown>> {
	/**
	 * Cleanup resources when adapter is destroyed.
	 */
	destroy(): void;

	/**
	 * Get the default values from the schema.
	 */
	getDefaults(): T;

	/**
	 * Get the schema definition used by this adapter.
	 */
	getSchema(): SchemaDefinition;

	/**
	 * Get the server-side state snapshot (for SSR).
	 * Only implemented by URL-based adapters.
	 *
	 * @returns Server state snapshot
	 */
	getServerSnapshot?(): StoreSnapshot<T>;

	/**
	 * Get the current state snapshot.
	 * Compatible with useSyncExternalStore's getSnapshot parameter.
	 *
	 * @returns Current state snapshot with version
	 */
	getSnapshot(): StoreSnapshot<T>;

	/**
	 * Get the unique table ID for this adapter.
	 */
	getTableId(): string;

	/**
	 * Check if updates are paused.
	 */
	isPaused(): boolean;

	/**
	 * Pause state updates (for live mode).
	 * While paused, setState calls are queued.
	 */
	pause(): void;

	/**
	 * Reset state to defaults.
	 *
	 * @param fields - Optional array of fields to reset. If omitted, resets all.
	 */
	reset(fields?: (keyof T)[]): void;

	/**
	 * Resume state updates.
	 * Applies any queued state changes.
	 */
	resume(): void;

	/**
	 * Update a single field value.
	 *
	 * @param key - Field key
	 * @param value - New value
	 */
	setField<K extends keyof T>(key: K, value: T[K]): void;

	/**
	 * Update state with partial values.
	 * Must use immutable updates (new references for changed values).
	 *
	 * @param partial - Partial state to merge
	 */
	setState(partial: Partial<T>): void;
	/**
	 * Subscribe to state changes.
	 * Compatible with useSyncExternalStore's subscribe parameter.
	 *
	 * @param listener - Callback to invoke when state changes
	 * @returns Unsubscribe function
	 */
	subscribe(listener: () => void): () => void;
}

/**
 * Options for creating an adapter
 */
export interface CreateAdapterOptions<T extends Record<string, unknown>> {
	/**
	 * Unique ID for this table (required for multi-table support)
	 */
	id: string;

	/**
	 * Initial state to override defaults
	 */
	initialState?: Partial<T>;
}

/**
 * Factory function type for creating adapters
 */
export type AdapterFactory<T extends Record<string, unknown>> = (
	schema: SchemaDefinition,
	options: CreateAdapterOptions<T>
) => StoreAdapter<T>;

/**
 * Available adapter types
 */
export type AdapterType = "nuqs" | "zustand";

/**
 * Internal adapter with additional methods for providers
 * @internal
 */
export interface InternalStoreAdapter<T extends Record<string, unknown>>
	extends StoreAdapter<T> {
	/**
	 * Internal method to get the state setter (used by nuqs adapter)
	 * @internal
	 */
	_getStateSetter?(): ((partial: Partial<T>) => void) | null;

	/**
	 * Internal method to set the state setter (used by nuqs adapter)
	 * @internal
	 */
	_setStateSetter?(setter: (partial: Partial<T>) => void): void;
	/**
	 * Internal method to sync external state (used by nuqs adapter)
	 * @internal
	 */
	_syncState?(state: T): void;
}
