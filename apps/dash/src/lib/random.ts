// biome-ignore-all lint/suspicious/noBitwiseOperators: hashing and the PRNG are bit arithmetic by design.
/** Deterministic randomness, so the same connection always shows the same
 * records and the same log always shows the same messages. */

export interface Rng {
	bool: (chance?: number) => boolean;
	hex: (length: number) => string;
	int: (min: number, max: number) => number;
	next: () => number;
	pick: <T>(items: readonly T[]) => T;
	sample: <T>(items: readonly T[], count: number) => T[];
	weighted: <T>(items: readonly (readonly [T, number])[]) => T;
}

const FNV_OFFSET = 2_166_136_261;
const FNV_PRIME = 16_777_619;
const UINT32 = 4_294_967_296;

export function hashString(input: string): number {
	let hash = FNV_OFFSET;
	for (const char of input) {
		hash ^= char.charCodeAt(0);
		hash = Math.imul(hash, FNV_PRIME);
	}
	return hash >>> 0;
}

/** mulberry32: small, fast, good enough for mock data. */
export function createRng(seed: string | number): Rng {
	let state = typeof seed === "number" ? seed >>> 0 : hashString(seed);
	const next = (): number => {
		state = (state + 0x6d_2b_79_f5) >>> 0;
		let t = state;
		t = Math.imul(t ^ (t >>> 15), t | 1);
		t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
		return ((t ^ (t >>> 14)) >>> 0) / UINT32;
	};
	const int = (min: number, max: number): number =>
		Math.floor(next() * (max - min + 1)) + min;
	const pick = <T>(items: readonly T[]): T =>
		items[int(0, items.length - 1)] as T;
	return {
		bool: (chance = 0.5) => next() < chance,
		hex: (length) => {
			let out = "";
			for (let i = 0; i < length; i += 1) {
				out += int(0, 15).toString(16);
			}
			return out;
		},
		int,
		next,
		pick,
		sample: (items, count) => {
			const pool = [...items];
			const out: (typeof items)[number][] = [];
			while (out.length < count && pool.length > 0) {
				out.push(
					pool.splice(int(0, pool.length - 1), 1)[0] as (typeof items)[number]
				);
			}
			return out;
		},
		weighted: (items) => {
			const total = items.reduce((sum, [, w]) => sum + w, 0);
			let roll = next() * total;
			for (const [item, weight] of items) {
				roll -= weight;
				if (roll <= 0) {
					return item;
				}
			}
			return (items.at(-1) as readonly [(typeof items)[number][0], number])[0];
		},
	};
}

const ID_ALPHABET =
	"0123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";

/** Short prefixed IDs in the style the API returns: vuln_2Xk9fQ. */
export function makeId(prefix: string, rng: Rng, length = 10): string {
	let out = "";
	for (let i = 0; i < length; i += 1) {
		out += ID_ALPHABET[rng.int(0, ID_ALPHABET.length - 1)];
	}
	return `${prefix}_${out}`;
}

/** A fresh random ID, for things the user creates. */
export function freshId(prefix: string, length = 10): string {
	return makeId(prefix, createRng(`${Date.now()}-${Math.random()}`), length);
}

export function uuid(rng: Rng): string {
	const h = rng.hex(32);
	return `${h.slice(0, 8)}-${h.slice(8, 12)}-4${h.slice(13, 16)}-a${h.slice(17, 20)}-${h.slice(20, 32)}`;
}
