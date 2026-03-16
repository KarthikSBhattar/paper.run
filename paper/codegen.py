from __future__ import annotations

from dataclasses import dataclass

from .ast import (
    AssignStmt,
    BinaryExpr,
    BinaryOp,
    BooleanExpr,
    CallExpr,
    Expr,
    ExprStmt,
    Function,
    IdentifierExpr,
    IfStmt,
    NoneExpr,
    NumberExpr,
    Program,
    ReturnStmt,
    StringExpr,
    UnaryExpr,
    UnaryOp,
    WhileStmt,
)


@dataclass(frozen=True)
class StringGlobal:
    symbol: str
    len_with_nul: int


class Codegen:
    def __init__(self, program: Program) -> None:
        self.program = program
        self.function_names = {function.name for function in program.functions}
        self.string_globals = collect_string_globals(program)

    def emit(self) -> str:
        parts = ["; paper.run generated LLVM IR\n", 'source_filename = "paper"\n\n']

        globals_by_symbol = sorted(self.string_globals.items(), key=lambda item: item[1].symbol)
        for value, global_info in globals_by_symbol:
            parts.append(
                f'{global_info.symbol} = private unnamed_addr constant [{global_info.len_with_nul} x i8] c"{llvm_escape_bytes(value)}"\n'
            )
        if globals_by_symbol:
            parts.append("\n")

        parts.append(runtime_prelude())

        for function in self.program.functions:
            parts.append(self.emit_function(function))
            parts.append("\n")

        parts.append(self.emit_entrypoint())
        return "".join(parts)

    def emit_function(self, function: Function) -> str:
        builder = IrBuilder(self.function_names, self.string_globals)
        params = ", ".join(f"%PaperValue %arg_{sanitize_symbol(param)}" for param in function.params)
        symbol = llvm_function_name(function.name)
        out = [f"define %PaperValue {symbol}({params}) {{\nentry:\n"]
        for param in function.params:
            builder.bind_param(param, out)

        terminated = builder.emit_block(function.body, out)
        if not terminated:
            none_value = builder.emit_none_literal(out)
            out.append(f"  ret %PaperValue {none_value}\n")
        out.append("}\n")
        return "".join(out)

    def emit_entrypoint(self) -> str:
        builder = IrBuilder(self.function_names, self.string_globals)
        out = ["define i32 @main() {\nentry:\n"]
        builder.emit_top_level_block(self.program.top_level, out)
        out.append("  ret i32 0\n")
        out.append("}\n")
        return "".join(out)


class IrBuilder:
    def __init__(self, function_names: set[str], string_globals: dict[str, StringGlobal]) -> None:
        self.next_value = 0
        self.function_names = function_names
        self.string_globals = string_globals
        self.locals: dict[str, str] = {}

    def emit_top_level_block(self, statements: list, out: list[str]) -> None:
        for stmt in statements:
            self.emit_top_level_stmt(stmt, out)

    def emit_top_level_stmt(self, stmt, out: list[str]) -> None:
        if isinstance(stmt, AssignStmt):
            self.emit_assign(stmt.name, stmt.expr, out)
            return
        if isinstance(stmt, IfStmt):
            self.emit_if_top_level(stmt.condition, stmt.then_body, stmt.else_body, out)
            return
        if isinstance(stmt, WhileStmt):
            self.emit_while_top_level(stmt.condition, stmt.body, out)
            return
        if isinstance(stmt, ExprStmt):
            self.emit_expr(stmt.expr, out)
            return
        raise AssertionError("top-level return should be rejected by semantic validation")

    def emit_block(self, statements: list, out: list[str]) -> bool:
        terminated = False
        for stmt in statements:
            if terminated:
                break
            terminated = self.emit_stmt(stmt, out)
        return terminated

    def emit_stmt(self, stmt, out: list[str]) -> bool:
        if isinstance(stmt, AssignStmt):
            self.emit_assign(stmt.name, stmt.expr, out)
            return False
        if isinstance(stmt, ExprStmt):
            self.emit_expr(stmt.expr, out)
            return False
        if isinstance(stmt, ReturnStmt):
            value = self.emit_expr(stmt.expr, out)
            out.append(f"  ret %PaperValue {value}\n")
            return True
        if isinstance(stmt, IfStmt):
            return self.emit_if(stmt.condition, stmt.then_body, stmt.else_body, out)
        if isinstance(stmt, WhileStmt):
            self.emit_while(stmt.condition, stmt.body, out)
            return False
        raise AssertionError(f"unsupported statement: {type(stmt).__name__}")

    def emit_expr(self, expr: Expr, out: list[str]) -> str:
        if isinstance(expr, BooleanExpr):
            return self.emit_bool_literal(expr.value, out)
        if isinstance(expr, NoneExpr):
            return self.emit_none_literal(out)
        if isinstance(expr, NumberExpr):
            return self.emit_number_literal(expr.value, out)
        if isinstance(expr, StringExpr):
            return self.emit_string_literal(expr.value, out)
        if isinstance(expr, IdentifierExpr):
            slot = self.locals[expr.name]
            temp = self.next_temp()
            out.append(f"  {temp} = load %PaperValue, ptr {slot}\n")
            return temp
        if isinstance(expr, UnaryExpr):
            value = self.emit_expr(expr.expr, out)
            if expr.op is UnaryOp.PLUS:
                return value
            if expr.op is UnaryOp.MINUS:
                return self.emit_numeric_unary("sub", value, out)
            return self.emit_not(value, out)
        if isinstance(expr, BinaryExpr):
            if expr.op in {BinaryOp.AND, BinaryOp.OR}:
                return self.emit_logical_op(expr.left, expr.op, expr.right, out)
            left = self.emit_expr(expr.left, out)
            right = self.emit_expr(expr.right, out)
            mapping = {
                BinaryOp.ADD: "paper_rt_add",
                BinaryOp.SUB: "paper_rt_sub",
                BinaryOp.MUL: "paper_rt_mul",
                BinaryOp.DIV: "paper_rt_div",
                BinaryOp.EQ: "paper_rt_eq",
                BinaryOp.NE: "paper_rt_ne",
                BinaryOp.LT: "paper_rt_lt",
                BinaryOp.LE: "paper_rt_le",
                BinaryOp.GT: "paper_rt_gt",
                BinaryOp.GE: "paper_rt_ge",
            }
            return self.emit_runtime_binary(mapping[expr.op], left, right, out)
        if isinstance(expr, CallExpr):
            if expr.callee == "print":
                return self.emit_print(expr.args, out)
            return self.emit_call(expr.callee, expr.args, out)
        raise AssertionError(f"unsupported expression: {type(expr).__name__}")

    def emit_call(self, callee: str, args: list[Expr], out: list[str]) -> str:
        rendered_args = [self.emit_expr(arg, out) for arg in args]
        temp = self.next_temp()
        signature = ", ".join(f"%PaperValue {arg}" for arg in rendered_args)
        out.append(f"  {temp} = call %PaperValue {llvm_function_name(callee)}({signature})\n")
        return temp

    def emit_assign(self, name: str, expr: Expr, out: list[str]) -> None:
        value = self.emit_expr(expr, out)
        slot = self.locals.get(name)
        if slot is None:
            slot = f"%slot_{sanitize_symbol(name)}"
            out.append(f"  {slot} = alloca %PaperValue\n")
            self.locals[name] = slot
        out.append(f"  store %PaperValue {value}, ptr {slot}\n")

    def bind_param(self, name: str, out: list[str]) -> None:
        slot = f"%slot_{sanitize_symbol(name)}"
        arg = f"%arg_{sanitize_symbol(name)}"
        out.append(f"  {slot} = alloca %PaperValue\n")
        out.append(f"  store %PaperValue {arg}, ptr {slot}\n")
        self.locals[name] = slot

    def emit_if(self, condition: Expr, then_body: list, else_body: list, out: list[str]) -> bool:
        cond_value = self.emit_expr(condition, out)
        cond_bool = self.emit_truthy_check(cond_value, out)
        then_label = self.next_label("if.then")
        else_label = self.next_label("if.else")
        end_label = self.next_label("if.end")
        out.append(f"  br i1 {cond_bool}, label %{then_label}, label %{else_label}\n")
        out.append(f"{then_label}:\n")
        then_terminated = self.emit_block(then_body, out)
        if not then_terminated:
            out.append(f"  br label %{end_label}\n")
        out.append(f"{else_label}:\n")
        if else_body:
            else_terminated = self.emit_block(else_body, out)
            if not else_terminated:
                out.append(f"  br label %{end_label}\n")
        else:
            else_terminated = False
            out.append(f"  br label %{end_label}\n")
        if not (then_terminated and else_terminated and else_body):
            out.append(f"{end_label}:\n")
        return bool(then_terminated and else_terminated and else_body)

    def emit_if_top_level(self, condition: Expr, then_body: list, else_body: list, out: list[str]) -> None:
        cond_value = self.emit_expr(condition, out)
        cond_bool = self.emit_truthy_check(cond_value, out)
        then_label = self.next_label("if.then")
        else_label = self.next_label("if.else")
        end_label = self.next_label("if.end")
        out.append(f"  br i1 {cond_bool}, label %{then_label}, label %{else_label}\n")
        out.append(f"{then_label}:\n")
        for stmt in then_body:
            self.emit_top_level_stmt(stmt, out)
        out.append(f"  br label %{end_label}\n")
        out.append(f"{else_label}:\n")
        for stmt in else_body:
            self.emit_top_level_stmt(stmt, out)
        out.append(f"  br label %{end_label}\n")
        out.append(f"{end_label}:\n")

    def emit_while(self, condition: Expr, body: list, out: list[str]) -> None:
        cond_label = self.next_label("while.cond")
        body_label = self.next_label("while.body")
        end_label = self.next_label("while.end")
        out.append(f"  br label %{cond_label}\n")
        out.append(f"{cond_label}:\n")
        cond_value = self.emit_expr(condition, out)
        cond_bool = self.emit_truthy_check(cond_value, out)
        out.append(f"  br i1 {cond_bool}, label %{body_label}, label %{end_label}\n")
        out.append(f"{body_label}:\n")
        body_terminated = self.emit_block(body, out)
        if not body_terminated:
            out.append(f"  br label %{cond_label}\n")
        out.append(f"{end_label}:\n")

    def emit_while_top_level(self, condition: Expr, body: list, out: list[str]) -> None:
        cond_label = self.next_label("while.cond")
        body_label = self.next_label("while.body")
        end_label = self.next_label("while.end")
        out.append(f"  br label %{cond_label}\n")
        out.append(f"{cond_label}:\n")
        cond_value = self.emit_expr(condition, out)
        cond_bool = self.emit_truthy_check(cond_value, out)
        out.append(f"  br i1 {cond_bool}, label %{body_label}, label %{end_label}\n")
        out.append(f"{body_label}:\n")
        for stmt in body:
            self.emit_top_level_stmt(stmt, out)
        out.append(f"  br label %{cond_label}\n")
        out.append(f"{end_label}:\n")

    def emit_print(self, args: list[Expr], out: list[str]) -> str:
        value = self.emit_expr(args[0], out)
        out.append(f"  call void @paper_print(%PaperValue {value})\n")
        return self.emit_none_literal(out)

    def emit_not(self, value: str, out: list[str]) -> str:
        temp = self.next_temp()
        out.append(f"  {temp} = call %PaperValue @paper_rt_not_value(%PaperValue {value})\n")
        return temp

    def emit_logical_op(self, left: Expr, op: BinaryOp, right: Expr, out: list[str]) -> str:
        result_slot = f"%logic_{self.next_value}"
        self.next_value += 1
        out.append(f"  {result_slot} = alloca %PaperValue\n")

        left_value = self.emit_expr(left, out)
        left_bool = self.emit_truthy_check(left_value, out)
        rhs_label = self.next_label("logic.rhs")
        short_label = self.next_label("logic.short")
        end_label = self.next_label("logic.end")

        if op is BinaryOp.AND:
            out.append(f"  br i1 {left_bool}, label %{rhs_label}, label %{short_label}\n")
            out.append(f"{short_label}:\n")
            out.append(f"  store %PaperValue {left_value}, ptr {result_slot}\n")
            out.append(f"  br label %{end_label}\n")
        else:
            out.append(f"  br i1 {left_bool}, label %{short_label}, label %{rhs_label}\n")
            out.append(f"{short_label}:\n")
            out.append(f"  store %PaperValue {left_value}, ptr {result_slot}\n")
            out.append(f"  br label %{end_label}\n")

        out.append(f"{rhs_label}:\n")
        right_value = self.emit_expr(right, out)
        out.append(f"  store %PaperValue {right_value}, ptr {result_slot}\n")
        out.append(f"  br label %{end_label}\n")

        out.append(f"{end_label}:\n")
        result = self.next_temp()
        out.append(f"  {result} = load %PaperValue, ptr {result_slot}\n")
        return result

    def emit_truthy_check(self, value: str, out: list[str]) -> str:
        temp = self.next_temp()
        out.append(f"  {temp} = call i1 @paper_rt_truthy(%PaperValue {value})\n")
        return temp

    def emit_number_literal(self, value: float, out: list[str]) -> str:
        temp = self.next_temp()
        out.append(f"  {temp} = call %PaperValue @paper_rt_make_number(double {format_number(value)})\n")
        return temp

    def emit_bool_literal(self, value: bool, out: list[str]) -> str:
        temp = self.next_temp()
        out.append(
            f"  {temp} = call %PaperValue @paper_rt_make_bool(i1 {'true' if value else 'false'})\n"
        )
        return temp

    def emit_none_literal(self, out: list[str]) -> str:
        temp = self.next_temp()
        out.append(f"  {temp} = call %PaperValue @paper_rt_make_none()\n")
        return temp

    def emit_string_literal(self, value: str, out: list[str]) -> str:
        global_info = self.string_globals[value]
        ptr = self.next_temp()
        out.append(
            f"  {ptr} = getelementptr inbounds [{global_info.len_with_nul} x i8], ptr {global_info.symbol}, i64 0, i64 0\n"
        )
        temp = self.next_temp()
        out.append(f"  {temp} = call %PaperValue @paper_rt_make_string(ptr {ptr})\n")
        return temp

    def emit_runtime_binary(self, name: str, left: str, right: str, out: list[str]) -> str:
        temp = self.next_temp()
        out.append(f"  {temp} = call %PaperValue @{name}(%PaperValue {left}, %PaperValue {right})\n")
        return temp

    def emit_numeric_unary(self, op: str, value: str, out: list[str]) -> str:
        zero = self.emit_number_literal(0.0, out)
        fn_name = {"sub": "paper_rt_sub"}[op]
        return self.emit_runtime_binary(fn_name, zero, value, out)

    def next_temp(self) -> str:
        temp = f"%tmp{self.next_value}"
        self.next_value += 1
        return temp

    def next_label(self, prefix: str) -> str:
        label = f"{prefix}.{self.next_value}"
        self.next_value += 1
        return label


def llvm_function_name(name: str) -> str:
    return f"@paper_{sanitize_symbol(name)}"


def sanitize_symbol(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in name)


def format_number(value: float) -> str:
    if value.is_integer():
        return f"{value:.1f}"
    return str(value)


def collect_string_globals(program: Program) -> dict[str, StringGlobal]:
    ordered: list[str] = []
    seen: set[str] = set()
    for function in program.functions:
        collect_strings_from_block(function.body, seen, ordered)
    collect_strings_from_block(program.top_level, seen, ordered)
    return {
        value: StringGlobal(symbol=f"@.paper.str.{index}", len_with_nul=len(value.encode()) + 1)
        for index, value in enumerate(ordered)
    }


def collect_strings_from_block(statements: list, seen: set[str], ordered: list[str]) -> None:
    for stmt in statements:
        if isinstance(stmt, (AssignStmt, ReturnStmt, ExprStmt)):
            collect_strings_from_expr(stmt.expr, seen, ordered)
        elif isinstance(stmt, IfStmt):
            collect_strings_from_expr(stmt.condition, seen, ordered)
            collect_strings_from_block(stmt.then_body, seen, ordered)
            collect_strings_from_block(stmt.else_body, seen, ordered)
        elif isinstance(stmt, WhileStmt):
            collect_strings_from_expr(stmt.condition, seen, ordered)
            collect_strings_from_block(stmt.body, seen, ordered)


def collect_strings_from_expr(expr: Expr, seen: set[str], ordered: list[str]) -> None:
    if isinstance(expr, StringExpr):
        if expr.value not in seen:
            seen.add(expr.value)
            ordered.append(expr.value)
        return
    if isinstance(expr, UnaryExpr):
        collect_strings_from_expr(expr.expr, seen, ordered)
        return
    if isinstance(expr, BinaryExpr):
        collect_strings_from_expr(expr.left, seen, ordered)
        collect_strings_from_expr(expr.right, seen, ordered)
        return
    if isinstance(expr, CallExpr):
        for arg in expr.args:
            collect_strings_from_expr(arg, seen, ordered)


def llvm_escape_bytes(value: str) -> str:
    out: list[str] = []
    for byte in value.encode():
        if byte == 0x5C:
            out.append("\\5C")
        elif byte == 0x22:
            out.append("\\22")
        elif 0x20 <= byte <= 0x7E:
            out.append(chr(byte))
        else:
            out.append(f"\\{byte:02X}")
    out.append("\\00")
    return "".join(out)


def runtime_prelude() -> str:
    return r"""%PaperValue = type { i8, double, ptr }

@.paper.print_number = private unnamed_addr constant [4 x i8] c"%g\0A\00"
@.paper.true = private unnamed_addr constant [5 x i8] c"True\00"
@.paper.false = private unnamed_addr constant [6 x i8] c"False\00"
@.paper.none = private unnamed_addr constant [5 x i8] c"None\00"

declare i32 @printf(ptr, ...)
declare i32 @puts(ptr)
declare i64 @strlen(ptr)
declare i32 @strcmp(ptr, ptr)

define %PaperValue @paper_rt_make_none() {
entry:
  %v0 = insertvalue %PaperValue undef, i8 0, 0
  %v1 = insertvalue %PaperValue %v0, double 0.0, 1
  %v2 = insertvalue %PaperValue %v1, ptr null, 2
  ret %PaperValue %v2
}

define %PaperValue @paper_rt_make_number(double %value) {
entry:
  %v0 = insertvalue %PaperValue undef, i8 1, 0
  %v1 = insertvalue %PaperValue %v0, double %value, 1
  %v2 = insertvalue %PaperValue %v1, ptr null, 2
  ret %PaperValue %v2
}

define %PaperValue @paper_rt_make_bool(i1 %value) {
entry:
  %payload = select i1 %value, double 1.0, double 0.0
  %v0 = insertvalue %PaperValue undef, i8 2, 0
  %v1 = insertvalue %PaperValue %v0, double %payload, 1
  %v2 = insertvalue %PaperValue %v1, ptr null, 2
  ret %PaperValue %v2
}

define %PaperValue @paper_rt_make_string(ptr %value) {
entry:
  %v0 = insertvalue %PaperValue undef, i8 3, 0
  %v1 = insertvalue %PaperValue %v0, double 0.0, 1
  %v2 = insertvalue %PaperValue %v1, ptr %value, 2
  ret %PaperValue %v2
}

define i1 @paper_rt_truthy(%PaperValue %value) {
entry:
  %tag = extractvalue %PaperValue %value, 0
  switch i8 %tag, label %number [
    i8 0, label %none
    i8 2, label %bool
    i8 3, label %string
  ]

none:
  ret i1 false

bool:
  %bool_payload = extractvalue %PaperValue %value, 1
  %bool_truth = fcmp one double %bool_payload, 0.0
  ret i1 %bool_truth

number:
  %number_payload = extractvalue %PaperValue %value, 1
  %number_truth = fcmp one double %number_payload, 0.0
  ret i1 %number_truth

string:
  %string_ptr = extractvalue %PaperValue %value, 2
  %string_len = call i64 @strlen(ptr %string_ptr)
  %string_truth = icmp ne i64 %string_len, 0
  ret i1 %string_truth
}

define %PaperValue @paper_rt_not_value(%PaperValue %value) {
entry:
  %truth = call i1 @paper_rt_truthy(%PaperValue %value)
  %negated = xor i1 %truth, true
  %result = call %PaperValue @paper_rt_make_bool(i1 %negated)
  ret %PaperValue %result
}

define %PaperValue @paper_rt_add(%PaperValue %lhs, %PaperValue %rhs) {
entry:
  %lhs_value = extractvalue %PaperValue %lhs, 1
  %rhs_value = extractvalue %PaperValue %rhs, 1
  %sum = fadd double %lhs_value, %rhs_value
  %result = call %PaperValue @paper_rt_make_number(double %sum)
  ret %PaperValue %result
}

define %PaperValue @paper_rt_sub(%PaperValue %lhs, %PaperValue %rhs) {
entry:
  %lhs_value = extractvalue %PaperValue %lhs, 1
  %rhs_value = extractvalue %PaperValue %rhs, 1
  %difference = fsub double %lhs_value, %rhs_value
  %result = call %PaperValue @paper_rt_make_number(double %difference)
  ret %PaperValue %result
}

define %PaperValue @paper_rt_mul(%PaperValue %lhs, %PaperValue %rhs) {
entry:
  %lhs_value = extractvalue %PaperValue %lhs, 1
  %rhs_value = extractvalue %PaperValue %rhs, 1
  %product = fmul double %lhs_value, %rhs_value
  %result = call %PaperValue @paper_rt_make_number(double %product)
  ret %PaperValue %result
}

define %PaperValue @paper_rt_div(%PaperValue %lhs, %PaperValue %rhs) {
entry:
  %lhs_value = extractvalue %PaperValue %lhs, 1
  %rhs_value = extractvalue %PaperValue %rhs, 1
  %quotient = fdiv double %lhs_value, %rhs_value
  %result = call %PaperValue @paper_rt_make_number(double %quotient)
  ret %PaperValue %result
}

define %PaperValue @paper_rt_eq(%PaperValue %lhs, %PaperValue %rhs) {
entry:
  %lhs_tag = extractvalue %PaperValue %lhs, 0
  %rhs_tag = extractvalue %PaperValue %rhs, 0
  %same_tag = icmp eq i8 %lhs_tag, %rhs_tag
  br i1 %same_tag, label %same_type, label %different_type

different_type:
  %different = call %PaperValue @paper_rt_make_bool(i1 false)
  ret %PaperValue %different

same_type:
  switch i8 %lhs_tag, label %compare_payload [
    i8 0, label %both_none
    i8 3, label %compare_string
  ]

both_none:
  %none_result = call %PaperValue @paper_rt_make_bool(i1 true)
  ret %PaperValue %none_result

compare_payload:
  %lhs_value = extractvalue %PaperValue %lhs, 1
  %rhs_value = extractvalue %PaperValue %rhs, 1
  %equal = fcmp oeq double %lhs_value, %rhs_value
  %result = call %PaperValue @paper_rt_make_bool(i1 %equal)
  ret %PaperValue %result

compare_string:
  %lhs_string = extractvalue %PaperValue %lhs, 2
  %rhs_string = extractvalue %PaperValue %rhs, 2
  %cmp = call i32 @strcmp(ptr %lhs_string, ptr %rhs_string)
  %equal_string = icmp eq i32 %cmp, 0
  %string_result = call %PaperValue @paper_rt_make_bool(i1 %equal_string)
  ret %PaperValue %string_result
}

define %PaperValue @paper_rt_ne(%PaperValue %lhs, %PaperValue %rhs) {
entry:
  %equal = call %PaperValue @paper_rt_eq(%PaperValue %lhs, %PaperValue %rhs)
  %result = call %PaperValue @paper_rt_not_value(%PaperValue %equal)
  ret %PaperValue %result
}

define %PaperValue @paper_rt_lt(%PaperValue %lhs, %PaperValue %rhs) {
entry:
  %lhs_value = extractvalue %PaperValue %lhs, 1
  %rhs_value = extractvalue %PaperValue %rhs, 1
  %cmp = fcmp olt double %lhs_value, %rhs_value
  %result = call %PaperValue @paper_rt_make_bool(i1 %cmp)
  ret %PaperValue %result
}

define %PaperValue @paper_rt_le(%PaperValue %lhs, %PaperValue %rhs) {
entry:
  %lhs_value = extractvalue %PaperValue %lhs, 1
  %rhs_value = extractvalue %PaperValue %rhs, 1
  %cmp = fcmp ole double %lhs_value, %rhs_value
  %result = call %PaperValue @paper_rt_make_bool(i1 %cmp)
  ret %PaperValue %result
}

define %PaperValue @paper_rt_gt(%PaperValue %lhs, %PaperValue %rhs) {
entry:
  %lhs_value = extractvalue %PaperValue %lhs, 1
  %rhs_value = extractvalue %PaperValue %rhs, 1
  %cmp = fcmp ogt double %lhs_value, %rhs_value
  %result = call %PaperValue @paper_rt_make_bool(i1 %cmp)
  ret %PaperValue %result
}

define %PaperValue @paper_rt_ge(%PaperValue %lhs, %PaperValue %rhs) {
entry:
  %lhs_value = extractvalue %PaperValue %lhs, 1
  %rhs_value = extractvalue %PaperValue %rhs, 1
  %cmp = fcmp oge double %lhs_value, %rhs_value
  %result = call %PaperValue @paper_rt_make_bool(i1 %cmp)
  ret %PaperValue %result
}

define void @paper_print(%PaperValue %value) {
entry:
  %tag = extractvalue %PaperValue %value, 0
  switch i8 %tag, label %print_number [
    i8 0, label %print_none
    i8 2, label %print_bool
    i8 3, label %print_string
  ]

print_none:
  %none_ptr = getelementptr inbounds [5 x i8], ptr @.paper.none, i64 0, i64 0
  %none_call = call i32 @puts(ptr %none_ptr)
  ret void

print_bool:
  %bool_value = extractvalue %PaperValue %value, 1
  %bool_truth = fcmp one double %bool_value, 0.0
  br i1 %bool_truth, label %print_true, label %print_false

print_true:
  %true_ptr = getelementptr inbounds [5 x i8], ptr @.paper.true, i64 0, i64 0
  %true_call = call i32 @puts(ptr %true_ptr)
  ret void

print_false:
  %false_ptr = getelementptr inbounds [6 x i8], ptr @.paper.false, i64 0, i64 0
  %false_call = call i32 @puts(ptr %false_ptr)
  ret void

print_number:
  %number_ptr = getelementptr inbounds [4 x i8], ptr @.paper.print_number, i64 0, i64 0
  %number_value = extractvalue %PaperValue %value, 1
  %number_call = call i32 (ptr, ...) @printf(ptr %number_ptr, double %number_value)
  ret void

print_string:
  %string_value = extractvalue %PaperValue %value, 2
  %string_call = call i32 @puts(ptr %string_value)
  ret void
}

"""
