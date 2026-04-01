"""
reader_ocgcore.py — Cliente mínimo de teste para zenonzard_rebirth

Se ocgcore.dll não estiver presente, baixa automaticamente do GitHub Releases.
Scripts Lua são lidos da pasta ./scripts/

Uso:
    python reader_ocgcore.py
"""

import ctypes
import sys
import os
import struct
import urllib.request

# ── Configuração ──────────────────────────────────────────────────────────────

DLL_PATH    = "ocgcore.dll"
DLL_URL     = "https://github.com/Badlakes/zenonzard_rebirth/releases/download/latest/ocgcore.dll"
SCRIPTS_DIR = "scripts"

# ── Constantes (de common.h) ──────────────────────────────────────────────────

LOCATION_DECK   = 0x01
LOCATION_HAND   = 0x02
LOCATION_MZONE  = 0x04  # Forces
LOCATION_SZONE  = 0x08  # Base
LOCATION_GRAVE  = 0x10
LOCATION_REMOVE = 0x20

POS_FACEUP_ATTACK   = 0x1
POS_FACEDOWN_ATTACK = 0x2
POS_FACEUP_DEFENSE  = 0x4
POS_FACEDOWN        = 0x8

TYPE_MONSTER = 0x1
TYPE_EFFECT  = 0x20

DUEL_TEST_MODE = 0x01

MSG_WIN      = 5
MSG_NEW_TURN = 40
MSG_NEW_PHASE= 41

PROCESSOR_END     = 0x20000000
PROCESSOR_WAITING = 0x10000000

# ── Download automático ───────────────────────────────────────────────────────

def ensure_dll():
    if os.path.exists(DLL_PATH):
        print(f"[DLL] Encontrada: {DLL_PATH}")
        return
    print(f"[DLL] Não encontrada. Baixando de:\n      {DLL_URL}")
    try:
        def progress(count, block, total):
            pct = min(count * block * 100 // total, 100)
            print(f"\r      {pct}%", end="", flush=True)
        urllib.request.urlretrieve(DLL_URL, DLL_PATH, reporthook=progress)
        print(f"\r[DLL] Download concluído: {DLL_PATH}")
    except Exception as e:
        print(f"\n[ERRO] Falha no download: {e}")
        print("       Faça o download manual e coloque ocgcore.dll nesta pasta.")
        sys.exit(1)

# ── Struct card_data (de card_data.h) ─────────────────────────────────────────

class CardData(ctypes.Structure):
    _fields_ = [
        ("code",        ctypes.c_uint32),
        ("alias",       ctypes.c_uint32),
        ("setcode",     ctypes.c_uint64),
        ("type",        ctypes.c_uint32),
        ("level",       ctypes.c_uint32),
        ("attribute",   ctypes.c_uint32),
        ("race",        ctypes.c_uint64),
        ("attack",      ctypes.c_int32),
        ("defense",     ctypes.c_int32),
        ("lscale",      ctypes.c_uint32),
        ("rscale",      ctypes.c_uint32),
        ("link_marker", ctypes.c_uint32),
    ]

# ── Callbacks ─────────────────────────────────────────────────────────────────

ScriptReaderFunc   = ctypes.CFUNCTYPE(ctypes.c_char_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_int))
CardReaderFunc     = ctypes.CFUNCTYPE(ctypes.c_uint32, ctypes.c_uint32, ctypes.POINTER(CardData))
MessageHandlerFunc = ctypes.CFUNCTYPE(ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32)

# Cache de scripts lidos do disco para manter os buffers vivos na memória
# (necessário para o GC não liberar antes da DLL terminar de usar)
_script_cache: dict[str, ctypes.Array] = {}

def script_reader(name: bytes, length) -> bytes | None:
    """Lê script Lua de ./scripts/<name>.lua e devolve o conteúdo."""
    script_name = name.decode("utf-8", errors="replace")
    filepath = os.path.join(SCRIPTS_DIR, script_name + ".lua")
    if script_name in _script_cache:
        buf = _script_cache[script_name]
        length[0] = len(buf)
        return buf
    if not os.path.exists(filepath):
        length[0] = 0
        return None
    with open(filepath, "rb") as f:
        data = f.read()
    buf = ctypes.create_string_buffer(data)
    _script_cache[script_name] = buf
    length[0] = len(data)
    return buf

def card_reader(code: int, data) -> int:
    """Preenche card_data. Por enquanto retorna monstro genérico para qualquer código."""
    data[0].code        = code
    data[0].alias       = 0
    data[0].setcode     = 0
    data[0].type        = TYPE_MONSTER | TYPE_EFFECT
    data[0].level       = 4
    data[0].attribute   = 0x10  # LIGHT
    data[0].race        = 0x2   # SPELLCASTER
    data[0].attack      = 1000
    data[0].defense     = 1000
    data[0].lscale      = 0
    data[0].rscale      = 0
    data[0].link_marker = 0
    return 1

def message_handler(pduel, msg_type: int) -> int:
    return 0

# ── Carrega DLL ───────────────────────────────────────────────────────────────

def load_dll(path: str):
    try:
        dll = ctypes.CDLL(path)
    except OSError as e:
        print(f"[ERRO] Não conseguiu carregar a DLL: {e}")
        sys.exit(1)

    dll.set_script_reader.argtypes   = [ScriptReaderFunc]
    dll.set_script_reader.restype    = None
    dll.set_card_reader.argtypes     = [CardReaderFunc]
    dll.set_card_reader.restype      = None
    dll.set_message_handler.argtypes = [MessageHandlerFunc]
    dll.set_message_handler.restype  = None

    dll.create_duel.argtypes = [ctypes.c_uint32]
    dll.create_duel.restype  = ctypes.c_void_p

    dll.start_duel.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    dll.start_duel.restype  = None

    dll.end_duel.argtypes = [ctypes.c_void_p]
    dll.end_duel.restype  = None

    dll.set_player_info.argtypes = [
        ctypes.c_void_p, ctypes.c_int32,
        ctypes.c_int32, ctypes.c_int32, ctypes.c_int32,
    ]
    dll.set_player_info.restype = None

    dll.new_card.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32,
        ctypes.c_uint8, ctypes.c_uint8,
        ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8,
    ]
    dll.new_card.restype = None

    dll.process.argtypes = [ctypes.c_void_p]
    dll.process.restype  = ctypes.c_uint32

    dll.get_message.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    dll.get_message.restype  = ctypes.c_int32

    dll.query_field_count.argtypes = [ctypes.c_void_p, ctypes.c_uint8, ctypes.c_uint8]
    dll.query_field_count.restype  = ctypes.c_int32

    return dll

# ── Helpers ───────────────────────────────────────────────────────────────────

def run_until_waiting(dll, pduel, max_ticks: int = 200) -> bool:
    """Processa ticks até a engine pedir input ou encerrar. Retorna True se esperando."""
    buf = ctypes.create_string_buffer(0x2000)
    for _ in range(max_ticks):
        result = dll.process(pduel)
        size   = dll.get_message(pduel, buf)
        if size > 0:
            msg_id = struct.unpack_from("B", buf.raw, 0)[0]
            if msg_id == MSG_WIN:
                print("[FIM] Duelo encerrado.")
                return False
        if result & PROCESSOR_END:
            return False
        if result & PROCESSOR_WAITING:
            return True
    return True

def visualize_field(dll, pduel):
    print("\n╔══════════════════════════════════╗")
    print("║          ESTADO DO CAMPO         ║")
    print("╠══════════════════════════════════╣")
    for p in range(2):
        label  = f"Jogador {p}"
        forces = dll.query_field_count(pduel, p, LOCATION_MZONE)
        base   = dll.query_field_count(pduel, p, LOCATION_SZONE)
        deck   = dll.query_field_count(pduel, p, LOCATION_DECK)
        hand   = dll.query_field_count(pduel, p, LOCATION_HAND)
        grave  = dll.query_field_count(pduel, p, LOCATION_GRAVE)
        print(f"║  {label}:")
        print(f"║    Forces (mzone): {forces:2d}/5  carta(s)")
        print(f"║    Base   (szone): {base:2d}/10 carta(s)")
        print(f"║    Deck:           {deck:2d} carta(s)")
        print(f"║    Mão:            {hand:2d} carta(s)")
        print(f"║    Trash:          {grave:2d} carta(s)")
        if p == 0:
            print("╠══════════════════════════════════╣")
    print("╚══════════════════════════════════╝\n")

def test_field_sizes(dll, pduel) -> bool:
    print("[TESTE] Verificando tamanho das zonas...\n")

    for seq in range(5):
        dll.new_card(pduel, 1000 + seq, 0, 0, LOCATION_MZONE, seq, POS_FACEUP_ATTACK)
    dll.new_card(pduel, 9999, 0, 0, LOCATION_MZONE, 5, POS_FACEUP_ATTACK)  # deve ser rejeitado
    forces = dll.query_field_count(pduel, 0, LOCATION_MZONE)

    for seq in range(10):
        dll.new_card(pduel, 2000 + seq, 0, 0, LOCATION_SZONE, seq, POS_FACEDOWN_ATTACK)
    dll.new_card(pduel, 9998, 0, 0, LOCATION_SZONE, 10, POS_FACEDOWN_ATTACK)  # deve ser rejeitado
    base = dll.query_field_count(pduel, 0, LOCATION_SZONE)

    ok_forces = forces == 5
    ok_base   = base   == 10
    print(f"  Forces: {forces}/5  → {'✓ OK' if ok_forces else '✗ ERRO'}")
    print(f"  Base:   {base}/10  → {'✓ OK' if ok_base   else '✗ ERRO'}")
    return ok_forces and ok_base

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ensure_dll()

    dll = load_dll(DLL_PATH)

    # Mantém referências vivas — o GC não pode coletar os callbacks enquanto a DLL os usa
    _sr = ScriptReaderFunc(script_reader)
    _cr = CardReaderFunc(card_reader)
    _mh = MessageHandlerFunc(message_handler)
    dll.set_script_reader(_sr)
    dll.set_card_reader(_cr)
    dll.set_message_handler(_mh)

    # Cria duelo
    pduel = dll.create_duel(42)
    if not pduel:
        print("[ERRO] create_duel retornou null.")
        sys.exit(1)

    # Jogadores: lp=12 representa Force Points máximos do Zenonzard
    dll.set_player_info(pduel, 0, 12, 5, 1)
    dll.set_player_info(pduel, 1, 12, 5, 1)

    # Decks iniciais
    for i in range(20):
        dll.new_card(pduel, 100 + i, 0, 0, LOCATION_DECK, 0, POS_FACEDOWN)
        dll.new_card(pduel, 100 + i, 1, 1, LOCATION_DECK, 0, POS_FACEDOWN)

    dll.start_duel(pduel, DUEL_TEST_MODE)
    run_until_waiting(dll, pduel)

    ok = test_field_sizes(dll, pduel)
    visualize_field(dll, pduel)

    dll.end_duel(pduel)

    print("═" * 36)
    print(f"  RESULTADO: {'PASSOU ✓' if ok else 'FALHOU ✗'}")
    print("═" * 36)

if __name__ == "__main__":
    main()
