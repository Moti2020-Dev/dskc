import wasmtime
import numpy as np
import os

WASM_PATH = os.path.join(os.path.dirname(__file__), "wasm", "sha3_wasm_bg.7b9ca65ddd.wasm")

class DeepSeekHash:
    def __init__(self, wasm_path=WASM_PATH):
        engine = wasmtime.Engine()
        with open(wasm_path, "rb") as f:
            wasm_bytes = f.read()
        module = wasmtime.Module(engine, wasm_bytes)
        self.store = wasmtime.Store(engine)
        linker = wasmtime.Linker(engine)
        linker.define_wasi()
        self.instance = linker.instantiate(self.store, module)
        self.memory = self.instance.exports(self.store)["memory"]

    def _write_to_memory(self, text: str) -> tuple[int, int]:
        encoded = text.encode("utf-8")
        length = len(encoded)
        ptr = self.instance.exports(self.store)["__wbindgen_export_0"](self.store, length, 1)
        memory_view = self.memory.data_ptr(self.store)
        for i, byte in enumerate(encoded):
            memory_view[ptr + i] = byte
        return ptr, length

    def calculate_hash(self, challenge: str, salt: str, difficulty: int, expire_at: int) -> float:
        prefix = f"{salt}_{expire_at}_"
        retptr = self.instance.exports(self.store)["__wbindgen_add_to_stack_pointer"](self.store, -16)
        try:
            ch_ptr, ch_len = self._write_to_memory(challenge)
            pfx_ptr, pfx_len = self._write_to_memory(prefix)
            self.instance.exports(self.store)["wasm_solve"](
                self.store, retptr, ch_ptr, ch_len, pfx_ptr, pfx_len, float(difficulty)
            )
            memory_view = self.memory.data_ptr(self.store)
            status = int.from_bytes(bytes(memory_view[retptr:retptr + 4]), byteorder="little", signed=True)
            if status == 0:
                return None  # no solution
            value_bytes = bytes(memory_view[retptr + 8:retptr + 16])
            return np.frombuffer(value_bytes, dtype=np.float64)[0]
        finally:
            self.instance.exports(self.store)["__wbindgen_add_to_stack_pointer"](self.store, 16)