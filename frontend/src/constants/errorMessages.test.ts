import { AxiosError, AxiosHeaders, type AxiosResponse } from "axios";
import { describe, expect, it } from "vitest";
import { extractApiErrorMessage } from "./errorMessages";

// Real AxiosError objects, built by hand -- no request is ever sent.
function responseError(status: number, data: unknown): AxiosError {
  const response: AxiosResponse = {
    status,
    statusText: "",
    data,
    headers: {},
    config: { headers: new AxiosHeaders() },
  };
  return new AxiosError("Request failed", "ERR_BAD_RESPONSE", undefined, undefined, response);
}

describe("extractApiErrorMessage", () => {
  it("translates a known English string detail", () => {
    expect(extractApiErrorMessage(responseError(404, { detail: "Schedule not found" }))).toBe(
      "此排課結果已不存在，請重新整理頁面",
    );
  });

  it("shows a backend Chinese (or any unknown) string detail as-is", () => {
    const detail = "此排課需求已被已發布或已封存的課表使用，無法修改";
    expect(extractApiErrorMessage(responseError(409, { detail }))).toBe(detail);
  });

  it("shows a custom validator's Chinese message from a 422 array", () => {
    const detail = [{ type: "value_error", msg: "Value error, 密碼至少需要 8 個字元" }];
    expect(extractApiErrorMessage(responseError(422, { detail }))).toBe("密碼至少需要 8 個字元");
  });

  it("maps 422 error types to short Chinese, de-duplicated and joined", () => {
    const detail = [
      { type: "missing", msg: "Field required" },
      { type: "missing", msg: "Field required" },
      { type: "int_parsing", msg: "Input should be a valid integer" },
    ];
    expect(extractApiErrorMessage(responseError(422, { detail }))).toBe("缺少必填欄位；欄位格式不正確");
  });

  it("uses the generic message for an unrecognised 422 item", () => {
    const detail = [{ type: "something_else", msg: "English only" }];
    expect(extractApiErrorMessage(responseError(422, { detail }))).toBe(
      "輸入的資料格式不正確，請檢查後再送出",
    );
  });

  it("shows at most three distinct 422 messages", () => {
    const detail = [
      { type: "missing" },
      { type: "int_parsing" },
      { type: "literal_error" },
      { type: "something_else" },
    ];
    expect(extractApiErrorMessage(responseError(422, { detail }))).toBe(
      "缺少必填欄位；欄位格式不正確；欄位值不在允許的選項內",
    );
  });

  it("reports no response at all as a connection problem", () => {
    expect(extractApiErrorMessage(new AxiosError("Network Error", "ERR_NETWORK"))).toBe(
      "無法連線到伺服器，請確認後端服務是否啟動。",
    );
    expect(extractApiErrorMessage(new Error("not axios"))).toBe(
      "無法連線到伺服器，請確認後端服務是否啟動。",
    );
  });

  it("reports a response in an unrecognised shape as a server problem", () => {
    expect(extractApiErrorMessage(responseError(500, "Internal Server Error"))).toBe(
      "伺服器回應異常，請稍後再試或聯絡管理員",
    );
    expect(extractApiErrorMessage(responseError(500, { message: "no detail" }))).toBe(
      "伺服器回應異常，請稍後再試或聯絡管理員",
    );
  });
});
