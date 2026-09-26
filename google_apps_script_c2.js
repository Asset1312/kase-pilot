/**
 * Google Apps Script C2 Bridge for Bybit Trading Bot
 * 
 * Инструкция по развертыванию:
 * 1. Откройте Google Диск (drive.google.com)
 * 2. Создайте новую Google Таблицу (назовите например "Bybit_Bot_Control")
 * 3. В верхнем меню выберите: Расширения (Extensions) -> Apps Script
 * 4. Замените весь код в редакторе на этот файл и сохраните (Ctrl+S).
 * 5. Нажмите: Развернуть (Deploy) -> Новое развертывание (New deployment)
 * 6. Выберите тип: Веб-приложение (Web app)
 * 7. В поле "У кого есть доступ" (Who has access) выберите: "Все" (Anyone)
 * 8. Нажмите "Развернуть", предоставьте разрешения и скопируйте Webhook URL.
 */

// Инициализация таблицы при первом запуске
function setupSheets() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  
  // Лист управления (Команды)
  var cmdSheet = ss.getSheetByName("Commands");
  if (!cmdSheet) {
    cmdSheet = ss.insertSheet("Commands");
    cmdSheet.appendRow(["Command ID", "Action", "Symbol", "Param", "Status", "Created At", "Executed At"]);
    cmdSheet.getRange("A1:G1").setFontWeight("bold").setBackground("#e2e8f0");
    // Пример команды
    cmdSheet.appendRow(["cmd_1", "STATUS", "ALL", "", "PENDING", new Date(), ""]);
  }
  
  // Лист мониторинга (Телеметрия бота)
  var statSheet = ss.getSheetByName("Telemetry");
  if (!statSheet) {
    statSheet = ss.insertSheet("Telemetry");
    statSheet.appendRow(["Metric", "Value", "Last Updated"]);
    statSheet.getRange("A1:C1").setFontWeight("bold").setBackground("#e2e8f0");
  }
}

// Обработка входящих GET запросов (Бот запрашивает новые команды)
function doGet(e) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var cmdSheet = ss.getSheetByName("Commands");
  
  if (!cmdSheet) {
    setupSheets();
    cmdSheet = ss.getSheetByName("Commands");
  }
  
  var data = cmdSheet.getDataRange().getValues();
  var pendingCommands = [];
  
  // Ищем все команды со статусом "PENDING"
  for (var i = 1; i < data.length; i++) {
    var row = data[i];
    var cmdId = row[0];
    var action = row[1];
    var symbol = row[2];
    var param = row[3];
    var status = row[4];
    
    if (status === "PENDING") {
      pendingCommands.push({
        row_index: i + 1,
        command_id: String(cmdId),
        action: String(action),
        symbol: String(symbol),
        param: String(param)
      });
    }
  }
  
  var response = {
    "status": "ok",
    "server_time": new Date().toISOString(),
    "pending_commands": pendingCommands
  };
  
  return ContentService.createTextOutput(JSON.stringify(response))
    .setMimeType(ContentService.MimeType.JSON);
}

// Обработка входящих POST запросов (Бот подтверждает команду или шлет статус)
function doPost(e) {
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var postData = JSON.parse(e.postData.contents);
    var type = postData.type; // "ACK_COMMAND" или "TELEMETRY"
    
    if (type === "ACK_COMMAND") {
      var cmdSheet = ss.getSheetByName("Commands");
      var cmdId = postData.command_id;
      var execStatus = postData.status || "EXECUTED"; // EXECUTED / FAILED
      var message = postData.message || "";
      
      var data = cmdSheet.getDataRange().getValues();
      for (var i = 1; i < data.length; i++) {
        if (String(data[i][0]) === String(cmdId)) {
          cmdSheet.getRange(i + 1, 5).setValue(execStatus); // Column E: Status
          cmdSheet.getRange(i + 1, 7).setValue(new Date() + " (" + message + ")"); // Column G: Executed At
          break;
        }
      }
      return ContentService.createTextOutput(JSON.stringify({"status": "ok", "ack": cmdId}))
        .setMimeType(ContentService.MimeType.JSON);
    }
    
    if (type === "TELEMETRY") {
      var statSheet = ss.getSheetByName("Telemetry");
      if (!statSheet) {
        setupSheets();
        statSheet = ss.getSheetByName("Telemetry");
      }
      
      // Очищаем и записываем актуальные метрики
      statSheet.getRange("A2:C50").clearContent();
      
      var metrics = [
        ["Bot Status", postData.bot_status || "ONLINE", new Date()],
        ["Total Equity (USD)", postData.total_equity || 0.0, new Date()],
        ["Free USDT", postData.free_usdt || 0.0, new Date()],
        ["Locked USDT", postData.locked_usdt || 0.0, new Date()],
        ["Active Mode", postData.active_mode || "NORMAL", new Date()],
        ["Primary (SUI) Free", postData.sui_free || 0.0, new Date()],
        ["Secondary (NEAR) Free", postData.near_free || 0.0, new Date()],
        ["Secondary (NEAR) Mode", postData.near_mode || "EXIT_ONLY", new Date()],
        ["Last Log", postData.last_log || "", new Date()]
      ];
      
      statSheet.getRange(2, 1, metrics.length, 3).setValues(metrics);
      
      return ContentService.createTextOutput(JSON.stringify({"status": "ok", "telemetry_updated": true}))
        .setMimeType(ContentService.MimeType.JSON);
    }
    
    return ContentService.createTextOutput(JSON.stringify({"status": "unknown_type"}))
      .setMimeType(ContentService.MimeType.JSON);
      
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({"status": "error", "error": err.toString()}))
      .setMimeType(ContentService.MimeType.JSON);
  }
}
