from Assembler2 import *
from EDAOBase import *
import ActionOpTableEDAO as edao

INVALID_ACTION_OFFSET = 0xFFFF
EMPTY_ACTION    = INVALID_ACTION_OFFSET

class CharacterPositionFactor:

    def __init__(self, fs = None):
        if fs == None:
            return

        self.X = fs.byte()
        self.Y = fs.byte()

class BattleActionScriptInfo:

    def __init__(self):
        self.ActionListOffset       = 0
        self.ChrPosFactorOffset     = 0
        self.Reserve                = 0
        self.PreloadChipList        = []
        self.ActionList             = []

        self.ChrPosFactor = []
        self.CraftActions = []

    def open(self, buf):
        if type(buf) == str:
            buf = open(buf, 'rb').read()

        fs = BytesStream()
        fs.openmem(buf)

        self.ActionListOffset   = fs.ushort()
        self.ChrPosFactorOffset = fs.ushort()
        self.Reserve            = fs.ushort()

        while True:
            index = fs.ulong()
            if index == 0xFFFFFFFF:
                break

            self.PreloadChipList.append(ChipFileIndex(index))

        fs.seek(self.ChrPosFactorOffset)
        for i in range(8):
            self.ChrPosFactor.append(CharacterPositionFactor(fs))

        fs.seek(self.ActionListOffset)
        while True:
            offset = fs.ushort()
            if offset == 0:
                break

            self.ActionList.append(offset)

        if len(self.ActionList) == 0:
            raise Exception('action number == 0')

        self.CraftActions = self.DisassembleCraftActions(fs)

        return

        for i in range(0x69, fs.size()):
            if i not in offsetlist:
                print('%X' % i)
                #input()

        input()

    def DiasmInstructionCallback(self, inst, fs):
        return

    def DisassembleCraftActions(self, fs):

        BuiltinCraftNames = \
        [
            'SysCraft_MagicEffect',
            'SysCraft_Stand',
            'SysCraft_Move',
            'SysCraft_UnderAttack',
            'SysCraft_Dead',
            'SysCraft_NormalAttack',
            'SysCraft_MagicChant',
            'SysCraft_MagicCast',
            'SysCraft_Win',
            'SysCraft_EnterBattle',
            'SysCraft_UseItem',
            'SysCraft_Stun',
            'SysCraft_Unknown2',
            'SysCraft_Reserve1',
            'SysCraft_Reserve2',
            'SysCraft_Counter',
        ]

        disasm = Disassembler(edao.edao_as_op_table, self.DiasmInstructionCallback)

        index = -1
        codeblocks = []
        blockoffsetmap = {}
        for func in self.ActionList:
            index += 1
            if func == INVALID_ACTION_OFFSET:
                codeblocks.append(CodeBlock(INVALID_ACTION_OFFSET))
                continue

            if func in blockoffsetmap:
                codeblocks.append(blockoffsetmap[func])
                continue

            fs.seek(func)
            block = disasm.DisasmBlock(fs)
            block.Name = ('Craft_%X' % block.Offset) if index >= len(BuiltinCraftNames) else BuiltinCraftNames[index]
            codeblocks.append(block)

            blockoffsetmap[func] = block

        return codeblocks

    def FormatCodeBlocks(self):
        disasm = Disassembler(edao.edao_as_op_table)

        blocks = []
        blockoffsetmap = {}
        for block in self.CraftActions:
            if block.Offset == INVALID_ACTION_OFFSET:
                continue

            if block.Offset in blockoffsetmap:
                continue

            blockoffsetmap[block.Offset] = True
            blocks.append(disasm.FormatCodeBlock(block))

        #for x in disasmtbl: print('%08X' % x)
        #input()

        return blocks

    def SaveToFile(self, filename):
        lines = []

        lines.append('from %s import *' % os.path.splitext(os.path.basename(__file__))[0])
        lines.append('')

        tmp = []
        for pos in self.ChrPosFactor:
            tmp.append('(%d, %d)' % (pos.X, pos.Y))

        name = os.path.splitext(os.path.basename(filename))[0]
        name = os.path.splitext(name)[0]

        lines.append('CreateBattleAction("%s", (%s))' % (name + '.dat', ', '.join(tmp)))
        lines.append('')
        lines.append('AddPreloadChip((')

        index = 0
        for chip in self.PreloadChipList:
            x = ('    "%s",' % chip.Name()).ljust(30)
            x += ' # %02X %d' % (index, index)
            lines.append(x)
            index += 1

        lines.append('))')
        lines.append('')

        lines.append('CraftAction((')
        index = 0
        for craft in self.CraftActions:
            name = ('"%s"'% craft.Name) if craft.Offset != INVALID_ACTION_OFFSET else 'EMPTY_ACTION'
            lines.append(('    %s,' % name).ljust(40) + ('# %02X %d' % (index, index)))
            index += 1

        lines.append('))')
        lines.append('')

        blocks = self.FormatCodeBlocks()

        for block in blocks:
            lines += block

        lines.append('SaveToFile()')
        lines.append('')

        txt = '\r\n'.join(lines)

        lines = txt.replace('\r\n', '\n').replace('\r', '\n').split('\n')

        for i in range(2, len(lines)):
            if lines[i] != '':
                lines[i] = '    %s' % lines[i]

        lines.insert(2, 'def main():')
        lines.append('TryInvoke(main)')
        lines.append('')

        fs = open(filename, 'wb')
        fs.write(''.encode('utf_8_sig'))
        fs.write('\r\n'.join(lines).encode('UTF8'))

def main():
    for f in sys.argv[1:]:
        asdat = BattleActionScriptInfo()
        asdat.open(f)
        asdat.SaveToFile(f + '.py')

TryInvoke(main)

############################################################################################
# support functions
############################################################################################

class BattleActionScriptInfoPort(BattleActionScriptInfo):
    FileName = ''
    Labels             = {}    # map<name, offset>
    DelayFixLabels     = []    # list of LabelEntry

    fs = None

actionfile = None

def label(labelname):
    pos = actionfile.fs.tell()
    plog('%08X: %s' % (pos, labelname))
    if pos in actionfile.Labels and actionfile.Labels[labelname] != pos:
        raise Exception('label name conflict')

    actionfile.Labels[labelname] = pos

def getlabel(name):
    return actionfile.Labels[name]

def CreateBattleAction(filename, ChrPosFactorList):

    if not IsTupleOrList(ChrPosFactorList):
        raise Exception('ChrPosFactorList must be list')

    global actionfile
    actionfile = BattleActionScriptInfoPort()

    actionfile.fs = BytesStream()
    actionfile.fs.open(filename, 'wb+')

    actionfile.FileName = filename
    for factor in ChrPosFactorList:
        f = CharacterPositionFactor()
        f.X = factor[0]
        f.Y = factor[1]
        actionfile.ChrPosFactor.append(f)

def AddPreloadChip(ChipFileList):

    if not IsTupleOrList(ChipFileList):
        raise Exception('ChipFileList must be list')

    fs = actionfile.fs

    fs.seek(6)

    for chip in ChipFileList:
        fs.wulong(ChipFileIndex(chip).Index())

    fs.wulong(0xFFFFFFFF)
    fs.wushort(0)

    actionfile.ChrPosFactorOffset = fs.tell()
    for factor in actionfile.ChrPosFactor:
        fs.wbyte(factor.X)
        fs.wbyte(factor.Y)

    actionfile.ActionListOffset = fs.tell()
    actionfile.ActionListOffset += 16 - actionfile.ActionListOffset % 16

    fs.seek(0)
    fs.wushort(actionfile.ActionListOffset)
    fs.wushort(actionfile.ChrPosFactorOffset)
    fs.seek(actionfile.ActionListOffset)

def CraftAction(CraftNameList):

    if not IsTupleOrList(CraftNameList):
        raise Exception('CraftNameList must be list')

    fs = actionfile.fs
    fs.seek(actionfile.ActionListOffset)

    actionfile.ActionList = list(CraftNameList)

    for craft in CraftNameList:
        if craft != INVALID_ACTION_OFFSET:
            actionfile.DelayFixLabels.append(LabelEntry(craft, fs.tell()))

        fs.wushort(INVALID_ACTION_OFFSET)

    fs.write(b'\x00' * (16 - len(CraftNameList) * 2 % 16))


for op, inst in edao.edao_as_op_table.items():

    func = []
    func.append('def %s(*args):' % inst.OpName)
    func.append('    return OpCodeHandler(0x%02X, args)' % inst.OpCode)
    func.append('')

    exec('\r\n'.join(func))

    opx = 'AS_%02X' % inst.OpCode

    if inst.OpName != opx:
        func[0] = 'def %s(*args):' % opx
        exec('\r\n'.join(func))


def DefaultOpCodeHandler(data):
    entry   = data.TableEntry
    fs      = data.FileStream
    inst    = data.Instruction
    oprs    = inst.OperandFormat
    values  = data.Arguments

    entry.Container.WriteOpCode(fs, inst.OpCode)

    if len(oprs) != len(values):
        raise Exception('operand: does not match values')

    for i in range(len(oprs)):
        entry.WriteOperand(data, oprs[i], values[i])

    return inst

def OpCodeHandlerPrivate(data):
    op = data.Instruction.OpCode
    entry = data.TableEntry

    handler = entry.Handler if entry.Handler != None else DefaultOpCodeHandler
    inst = handler(data)

    if inst == None:
        inst = DefaultOpCodeHandler(data)

    return inst

def OpCodeHandler(op, args):
    entry = edao.edao_as_op_table[op]
    fs = actionfile.fs

    data = HandlerData(HANDLER_REASON_GENERATE)
    data.Instruction    = Instruction(op)
    data.Arguments      = list(args)
    data.FileStream     = fs
    data.TableEntry     = entry

    data.Instruction.OperandFormat = entry.Operand

    data.FileStream = BytesStream().openmem()

    #print(entry.OpName)
    inst = OpCodeHandlerPrivate(data)

    offset = actionfile.fs.tell()
    for lb in inst.Labels:
        actionfile.DelayFixLabels.append(LabelEntry(lb.Label, lb.Offset + offset))

    data.FileStream.seek(0)
    actionfile.fs.write(data.FileStream.read())

    return inst

def SaveToFile():
    fs = actionfile.fs

    for lb in actionfile.DelayFixLabels:
        fs.seek(lb.Offset)
        fs.wushort(getlabel(lb.Label))